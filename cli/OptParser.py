#!/usr/bin/python
# coding:utf-8

import re
import sys
import copy
import getopt


class OptParser:
    StateNone = 0
    StateParam = 1
    StateBrace = 2
    StateBracket = 3

    # initiator
    def __init__(self):
        self._single_opts = ""
        self._multi_opts = []
        self._mode_list = []

    # parse single opt
    def _parse_single_opt(self, substr):
        if re.match("^-[a-zA-Z]$", substr):
            if (substr[1] + ":") in self._single_opts:
                # conflict
                raise ValueError("Confilict with existing argument")
            elif substr[1] not in self._single_opts:
                self._single_opts += substr[1]

            return substr
        elif re.match("^-[a-zA-Z]=$", substr):
            if (substr[1] + ":") not in self._single_opts:
                if substr[1] in self._single_opts:
                    # conflict
                    raise ValueError("Confilict with existing argument")
                else:
                    self._single_opts += (substr[1] + ":")

            return substr.strip("=")
        elif re.match("^--[a-zA-Z][a-zA-Z-]+$", substr):
            if (substr[2:] + "=") in self._multi_opts:
                # conflict
                raise ValueError("Confilict with existing argument")
            elif substr[2:] not in self._multi_opts:
                self._multi_opts.append(substr[2:])

            return substr
        elif re.match("^--[a-zA-Z][a-zA-Z-]+=$", substr):
            if substr[2:-1] in self._multi_opts:
                # conflict
                raise ValueError("Confilict with existing argument")
            elif substr[2:] not in self._multi_opts:
                self._multi_opts.append(substr[2:])

            return substr.strip("=")

        raise ValueError("Wrong option key: %s" % substr)

    # parse mode block in brace
    def _parse_inner_brace(self, str_in_brace):
        mode_list = []
        substr = ""
        brace_cnt = 0
        bracket_cnt = 0
        for i in str_in_brace:
            if i == "|" and brace_cnt == 0 and bracket_cnt == 0:
                # split mutual branch in brace
                if substr == "":
                    raise ValueError("Empty mutual branch in brace")
                else:
                    mode_list += self._parse_mode(substr)
                    substr = ""
                    brace_cnt = 0
                    bracket_cnt = 0
            elif i == "{":
                # front brace(nesting brace)
                brace_cnt += 1
                substr += i
            elif i == "}":
                # back brace
                if brace_cnt <= 0:
                    raise ValueError("Wrong brace pair")

                brace_cnt -= 1
                substr += i
            elif i == "[":
                # front bracket
                brace_cnt += 1
                substr += i
            elif i == "]":
                # back bracket
                if brace_cnt <= 0:
                    raise ValueError("Wrong bracket pair")

                brace_cnt -= 1
                substr += i
            else:
                substr += i

        # last mutual brach
        if substr == "":
            raise ValueError("Empty mutual branch in brace")
        else:
            mode_list += self._parse_mode(substr)

        return mode_list

    # main parse
    def _parse_mode(self, mode_string):
        mode_list = [[]]
        substr = ""
        brace_cnt = 0
        bracket_cnt = 0
        state = OptParser.StateNone
        for i in mode_string:
            if state == OptParser.StateNone:
                # current state is
                if i == "{":
                    # StateNone -> StateBrace
                    brace_cnt += 1
                    state = OptParser.StateBrace
                elif i == "[":
                    # StateNone -> StateBracket
                    bracket_cnt += 1
                    state = OptParser.StateBracket
                else:
                    # StateNone -> StateParam
                    state = OptParser.StateParam
                    substr += i
            elif state == OptParser.StateParam:
                if i == ",":
                    # StateParam -> StateNone
                    opt = self._parse_single_opt(substr)
                    for mode in mode_list:
                        mode.append(opt)
                    substr = ""
                    state = OptParser.StateNone
                elif i == "{":
                    # StateParam -> StateBrace
                    opt = self._parse_single_opt(substr)
                    for mode in mode_list:
                        mode.append(opt)
                    substr = ""
                    brace_cnt += 1
                    state = OptParser.StateBrace
                elif i == "[":
                    # StateParam -> StateBracket
                    opt = self._parse_single_opt(substr)
                    for mode in mode_list:
                        mode.append(opt)
                    substr = ""
                    bracket_cnt += 1
                    state = OptParser.StateBracket
                else:
                    substr += i
            elif state == OptParser.StateBrace:
                if i == "{":
                    # front brace(nesting brace)
                    brace_cnt += 1
                    substr += i
                elif i == "}":
                    # back brace
                    if brace_cnt <= 0:
                        raise ValueError("Wrong brace pair")

                    brace_cnt -= 1
                    if brace_cnt == 0:
                        # end of block in brace
                        # StateBrace -> StateNone
                        sub_mode_list = self._parse_inner_brace(substr)
                        tmp_mode_list = mode_list
                        mode_list = []
                        for sub_mode in sub_mode_list:
                            for tmp_mode in tmp_mode_list:
                                mode_list.append(tmp_mode + sub_mode)

                        substr = ""
                        state = OptParser.StateNone
                    else:
                        substr += i
                else:
                    substr += i
            elif state == OptParser.StateBracket:
                if i == "[":
                    # front bracket(nesting bracket)
                    bracket_cnt += 1
                    substr += i
                elif i == "]":
                    # back bracket
                    if bracket_cnt <= 0:
                        raise ValueError("Wrong bracket pair")

                    bracket_cnt -= 1
                    if bracket_cnt == 0:
                        # end of block in bracket
                        # StateBracket -> StateNone
                        sub_mode_list = self._parse_mode(substr)
                        tmp_mode_list = copy.deepcopy(mode_list)
                        for sub_mode in sub_mode_list:
                            for tmp_mode in tmp_mode_list:
                                mode_list.append(tmp_mode + sub_mode)

                        substr = ""
                        state = OptParser.StateNone
                    else:
                        substr += i
                else:
                    substr += i

        if state == OptParser.StateParam:
            # StateParam -> StateNone
            opt = self._parse_single_opt(substr)
            for mode in mode_list:
                mode.append(opt)
            state = OptParser.StateNone

        if state != OptParser.StateNone:
            # state machine stopped with wrong state
            raise ValueError("Parse mode list error: wrong end state")

        return mode_list

    # append command mode
    def append(self, mode_name, mode_string):
        if not isinstance(mode_name, str) or not isinstance(mode_string, str):
            raise TypeError("mode_name and mode_string must be 'str' object")

        # has special character?
        if re.findall(r"[^a-zA-Z0-9{|}\[\],=-]+", mode_string):
            raise ValueError("mode_string contains special character")

        # parse and save mode list
        mode_list = self._parse_mode(mode_string)
        for i in mode_list:
            self._mode_list.append([mode_name, i])
            # print i

    # parse argument list
    def parse(self, arg_list):
        try:
            opts, args = getopt.getopt(arg_list, self._single_opts, self._multi_opts)
        except getopt.GetoptError, err:
            raise ValueError("Parse error: %s" % err.msg)

        # has redundant arguments?
        if len(args) != 0:
            raise ValueError("Redundant arguments: %s" % args)

        # has duplicte arguments?
        key_list = [k for k, v in opts]
        if len(key_list) != len(set(key_list)):
            raise ValueError("Duplicate arguments")

        # match mode
        for mode_name, mode_key_list in self._mode_list:
            if set(mode_key_list) == set(key_list):
                return mode_name, opts

        raise ValueError("Can't match any command mode")


if __name__ == "__main__":
    try:
        # prepare OptParser
        parser = OptParser()
        parser.append("help", "{-h|--help}")
        parser.append("ftp_create", "--create,-p=[--user=,-a=]")
        parser.append("ftp_query", "--query[{-p=|--service}]")
        parser.append("ftp_set", "--set{-p=,--user=,-a=|--limit=}")
        parser.append("ftp_delete", "--delete,-p=[--user=]")
        parser.append("ftp_start", "--start")
        parser.append("ftp_stop", "--stop")
        parser.append("ftp_status", "--status")

        # actually parse arguments
        m_name, m_opts = parser.parse(sys.argv[1:])
    except Exception, e:
        print e
        sys.exit(1)

    # print parse result
    print m_name
    print m_opts
