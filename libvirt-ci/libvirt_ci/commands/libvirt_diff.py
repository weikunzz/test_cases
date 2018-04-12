"""
Get differences between libvirt versions and show them in a PDF file.
"""
import logging
import ast
import collections
import glob
import json
import os
import re
import shutil
import tempfile

import git
import graphviz
import pycparser

from libvirt_ci import utils

from libvirt_ci.data import RESOURCE_PATH, REPO_PATH

LOGGER = logging.getLogger(__name__)


def preprocess_source_file(path):
    """
    Preprocess source file to replace defined names
    """
    with open(path) as src_fp:
        src_code = src_fp.read()

    code_lines = []
    for line in src_code.splitlines():
        code_lines.append(line)

    processed_code = pycparser.preprocess_file(
        path, cpp_path='gcc', cpp_args=['-E', '-P'])

    new_lines = []
    for line in processed_code.splitlines():
        new_lines.append(line)
    return '\n'.join(new_lines)


def prepare_source_file(src_dir, tmp_dir, files):
    """
    Collect useful lines in source file and concatenate them into one
    """
    code_lines = ['#define N_(text) text']

    # Move common headers to the top of the list for including useful macros
    # before referencing them
    common_headers = []
    for path in files:
        if path.endswith(('virsh.h', 'vsh.h')):
            common_headers.append(path)
    for path in common_headers:
        files.pop(files.index(path))
    for path in common_headers:
        files.insert(0, path)

    for file_name in files:
        src_path = os.path.join(src_dir, file_name)

        with open(src_path) as src_fp:
            src_code = src_fp.read()

        # Process code
        collecting_declare = False
        collecting_define = False
        for line in src_code.splitlines():
            # Check if we should start collection
            if re.match(r"#\s*define\s*(VIRSH_|VSH_).*", line):
                collecting_define = True
            if re.match(
                    r"^(static\s+)?(const\s+)?vshCmd(Def|OptDef|Info|Grp).*{$",
                    line):
                collecting_declare = True

            # Collect one line
            if collecting_declare or collecting_define:
                code_lines.append(line)

            # Check if we should stop collection
            if collecting_declare and line.startswith('};'):
                collecting_declare = False
            if collecting_define:
                if not line.strip():
                    collecting_define = False

    tmp_path = os.path.join(tmp_dir, 'virsh.c')
    with open(tmp_path, 'w') as tgt_fp:
        tgt_fp.write('\n'.join(code_lines))


def parse_code(libvirt_path):
    """
    Find all virsh related code and parse them into AST.
    """

    # Define struct for all command groups, sub-commands and options
    c_code = """
typedef enum {
    VSH_OT_BOOL,
    VSH_OT_STRING,
    VSH_OT_INT,
    VSH_OT_DATA,
    VSH_OT_ARGV,
    VSH_OT_ALIAS,
} vshCmdOptType;

typedef char **(*vshCompleter)(void *opaque, unsigned int flags);
typedef struct _vshCmdOptDef vshCmdOptDef;
typedef struct _vshCmdInfo vshCmdInfo;
typedef struct _vshCmdDef vshCmdDef;
typedef struct _vshCmdGrp vshCmdGrp;

struct _vshCmdOptDef {
    const char *name;
    vshCmdOptType type;
    unsigned int flags;
    const char *help;
    vshCompleter completer;
    unsigned int completer_flags;
};

struct _vshCmdInfo {
    const char *name;
    const char *data;
};

struct _vshCmdDef {
    const char *name;
    const vshCmdOptDef *opts;
    const vshCmdInfo *info;
    unsigned int flags;
    const char *alias;
};

struct _vshCmdGrp {
    const char *name;
    const char *keyword;
    const vshCmdDef *commands;
};

"""

    src_dir = os.path.join(libvirt_path, 'tools')
    tmp_dir = tempfile.mkdtemp(prefix='libvirt-diff-')

    try:
        files = glob.glob("%s/tools/*.[ch]" % libvirt_path)
        files.extend(glob.glob("%s/src/virsh.c" % libvirt_path))

        prepare_source_file(src_dir, tmp_dir, files)

        for path in glob.glob('%s/*.c' % tmp_dir):
            code = preprocess_source_file(os.path.join(path))
            c_code += code
    finally:
        shutil.rmtree(tmp_dir)

    # Save last generated code file for debugging
    last_code_file = os.path.join(tempfile.tempdir, 'libvirt-diff-last-code.c')
    with open(last_code_file, 'w') as fp_ast:
        fp_ast.write(c_code)

    parser = pycparser.c_parser.CParser()
    c_ast = parser.parse(c_code)
    return c_ast


def _extract_declare(init_lists, keys):
    infos = []
    for _, info_type in init_lists.children():
        info = {}
        for idx, (_, item) in enumerate(info_type.children()):
            if isinstance(item, pycparser.c_ast.NamedInitializer):
                key = item.name[0].name
                item = item.expr
            else:
                key = keys[idx]

            if isinstance(item, pycparser.c_ast.Constant):
                value = ast.literal_eval(item.value)
            elif isinstance(item, pycparser.c_ast.ID):
                value = item.name
            elif isinstance(item, pycparser.c_ast.BinaryOp):
                if item.op == '|':
                    value = [item.left.name, item.right.name]
                elif item.op == '<<':
                    value = (ast.literal_eval(item.left.value) <<
                             ast.literal_eval(item.right.value))
                else:
                    value = item.show()
            elif isinstance(item, pycparser.c_ast.Cast):
                # process (void *)0
                expr = item.children()[1][1].value
                assert expr == '0'
                value = int(expr)
            elif isinstance(item, pycparser.c_ast.FuncCall):
                # process gettext_noop("str")
                assert item.children()[0][1].name in ('gettext_noop', 'N_')
                expr = item.children()[1][1].children()[0][1]
                if isinstance(expr, pycparser.c_ast.Constant):
                    value = expr.value
                else:
                    value = expr
            else:
                LOGGER.info(item.show())
                raise Exception("Unknown type %s" % type(item))

            info[key] = value

            if key not in keys:
                LOGGER.warning("Unknown key %s", key)

        infos.append(info)
    if not all(value in [0, '0', 'NULL']
               for _, value in infos[-1].items()):
        raise Exception("Found non-zero ending entry: %s" % infos[-1])
    del infos[-1]
    return infos


def extract_info(c_ast):
    """
    Extract virsh commands info from AST.
    """

    cmd_infos = {}
    cmd_opts = {}
    all_groups = collections.defaultdict(dict)
    for _, child in c_ast.children():
        if not isinstance(child, pycparser.c_ast.Decl):
            continue
        if not isinstance(child.children()[0][1], pycparser.c_ast.ArrayDecl):
            continue
        array_decl = child.children()[0][1]
        init_lists = child.children()[1][1]
        cls = array_decl.type.type.names[0]
        if cls == 'vshCmdInfo':
            info_name = array_decl.type.declname
            cmd_infos[info_name] = _extract_declare(
                init_lists, keys=['name', 'data'])
        elif cls == 'vshCmdOptDef':
            opt_name = array_decl.type.declname
            cmd_opts[opt_name] = _extract_declare(
                init_lists, keys=['name', 'type', 'flags', 'help'])
        elif cls == 'vshCmdDef':
            group_name = array_decl.type.declname
            all_groups[group_name]['commands'] = _extract_declare(
                init_lists,
                keys=['name', 'handler', 'opts', 'info', 'flags', 'alias'])
        elif cls == 'vshCmdGrp':
            groups = _extract_declare(
                init_lists, keys=['name', 'keyword', 'commands'])
            for group in groups:
                all_groups[group['commands']]['name'] = group['name']
                all_groups[group['commands']]['keyword'] = group['keyword']

    for group_name, group in all_groups.items():
        for cmd in group['commands']:
            # Alias don't have info nor options
            if 'flags' in cmd and cmd['flags'] == 'VSH_CMD_FLAG_ALIAS':
                continue
            cmd_info_name = cmd['info']
            cmd_opts_name = cmd['opts']
            cmd_info = cmd_infos[cmd_info_name]
            if cmd_opts_name in [0, 'NULL']:
                cmd_opt = {}
            else:
                cmd_opt = cmd_opts[cmd_opts_name]
            cmd['info'] = cmd_info
            cmd['opts'] = cmd_opt
    return all_groups


def get_info(repo, tag):
    """
    Get all needed information from a specific tag in repo
    """
    tag = tag.splitlines()[0]
    LOGGER.info('Getting info of %s', tag)
    repo.git.reset(tag, hard=True)
    repo.git.clean('-fdx')

    c_ast = parse_code(repo.working_dir)
    info = extract_info(c_ast)
    return info


def get_diff(old_info, new_info):
    """
    Get the difference between two builds
    """
    old_cmds = {}
    new_cmds = {}
    old_info_has_group = True
    for group_name, group in old_info.items():
        group_keyword = None
        if 'keyword' in group:
            group_keyword = group['keyword']
        else:
            old_info_has_group = False
        for cmd in group['commands']:
            old_cmds[(group_keyword, cmd['name'])] = cmd
    for group_name, group in new_info.items():
        group_keyword = None
        if old_info_has_group and 'keyword' in group:
            group_keyword = group['keyword']
        for cmd in group['commands']:
            new_cmds[(group_keyword, cmd['name'])] = cmd

    add_cmds = set(new_cmds) - set(old_cmds)
    del_cmds = set(old_cmds) - set(new_cmds)

    diff = ''
    for cmd in set(old_cmds) & set(new_cmds):
        group_name, cmd_name = cmd
        if group_name:
            cmd_name = '%s.%s' % (group_name, cmd_name)
        try:
            if 'alias' in new_cmds[cmd] and 'alias' not in old_cmds[cmd]:
                diff += 'alias: %s.%s -> %s.%s\n' % (
                    group_name, new_cmds[cmd]['alias'],
                    group_name, new_cmds[cmd]['name'])
            if 'opts' in new_cmds[cmd] and 'opts' in old_cmds[cmd]:
                new_opts = set(opt['name'] for opt in new_cmds[cmd]['opts'])
                old_opts = set(opt['name'] for opt in old_cmds[cmd]['opts'])
                add_opts = new_opts - old_opts
                del_opts = old_opts - new_opts

                if add_opts:
                    for opt in add_opts:
                        diff += '%s: + %s\n' % (cmd_name, opt)
                if del_opts:
                    for opt in del_opts:
                        diff += '%s: - %s\n' % (cmd_name, opt)
        except TypeError:
            pass

    if add_cmds:
        for group_name, cmd_name in add_cmds:
            if group_name:
                cmd_name = '%s.%s' % (group_name, cmd_name)
            diff += 'cmd: + %s\n' % cmd_name
    if del_cmds:
        for group_name, cmd_name in del_cmds:
            if group_name:
                cmd_name = '%s.%s' % (group_name, cmd_name)
            diff += 'cmd: - %s\n' % cmd_name

    if diff:
        print diff
    return diff


def prepare_repo():
    """
    Prepare git repo to get all the information needed
    """
    utils.update_git_repo(
        'libvirt-rhel',
        'http://git.host.prod.eng.bos.redhat.com/git/libvirt-rhel.git')
    repo_dir = os.path.join(REPO_PATH, 'libvirt-rhel')
    return git.Repo(repo_dir)


def draw_graph(infos, edges, output_file):
    """
    Draw a graph in PDF format shows the changes between all libvirt builds
    """
    graph_attr = {
        'rankdir': 'BT',
    }
    node_attr = {
        'shape': 'box',
    }
    dot = graphviz.Digraph(graph_attr=graph_attr, node_attr=node_attr)
    for tag in infos.keys():
        dot.node(tag, tag)

    for last_tag, tag in edges:
        if (tag in infos and infos[tag] and
                last_tag in infos and infos[last_tag]):
            LOGGER.info("%s -> %s", last_tag, tag)
            diff = get_diff(infos[last_tag], infos[tag])
            dot.edge(last_tag, tag, diff)
        else:
            dot.edge(last_tag, tag)
    dot.render(os.path.splitext(output_file)[0])


def run(params):
    """
    Main function for get difference between libvirt versions.
    """
    repo = prepare_repo()

    branches = []
    for line in repo.git.branch(all=True).splitlines():
        match = re.search(r'(remotes/origin/\S+)', line)
        if match:
            branch = match.group(1)
            if 'HEAD' in branch:
                continue
            branches.append(branch)

    info_path = os.path.join(RESOURCE_PATH, 'libvirt-diff.json')
    try:
        with open(info_path) as info_fp:
            infos = json.load(info_fp)
    except (OSError, IOError) as details:
        LOGGER.info("Can't locate info file: %s", details)
        LOGGER.info("Generating a new info file: %s", info_path)
        infos = {}

    edges = set()
    counter = 0
    for branch in sorted(branches):
        last_tag = None
        for line in repo.git.log(
                branch,
                simplify_by_decoration=True,
                pretty="format:'%d'").splitlines()[::-1]:
            tag = '\n'.join(re.findall(r'tag: ([^),]+)', line))
            if tag and tag not in infos:
                infos[tag] = get_info(repo, tag)
                counter += 1
                if counter % 100 == 0:
                    with open(info_path, 'w') as info_fp:
                        json.dump(infos, info_fp, indent=4)
            if last_tag:
                edges.add((last_tag, tag))
            last_tag = tag

    draw_graph(infos, edges, params.output)


def parse(parser):
    """
    Parse arguments for get difference between libvirt versions.
    """
    parser.add_argument(
        '--output', dest='output', action='store',
        default='libvirt-diff.pdf',
        help='Path to the output PDF file')
