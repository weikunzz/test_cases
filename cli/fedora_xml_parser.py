#!/usr/bin/python
# coding:utf-8

from lxml import etree
from OptParser import OptParser
import sys
import os
import re
from icfs_util import ip_format


def usage():
    print '''icfs_xml_parser ---- +--query--+ ------ --file file_path------ +--key key_value+--------------------------
                                                                            '--all          '
                                  '--update--'------ --file file_path------ --key key_value ---- --value update_value--
          Functions: parse the xml configuration file
Options:
  --query: query the config element in xml file specified
  --file:  the xml file path
  --key:   the name of query element(if more than one level, using / to split e.g. Protocol/CIFS)
  --all:   list all config element in specified xml file
  --value: used to update the key element value in xml file
  --update using the value update the specified key element in xml file
Exit status:
  0 if executed successfully
  1 if executed unsuccessfully
                                  '''


class IcfsXmlParser:
    def __init__(self):
        pass

    def query_all_config_element(self):
        pass

    def get_value_by_name(self, query_name):
        pass

    def set_value_by_name(self, config_name, config_value, set_file):
        pass


class HadoopXmlParser(IcfsXmlParser):

    def __init__(self, file_name):
        IcfsXmlParser.__init__(self)
        self.file_name = file_name
        self.config_element = {}
        if os.path.exists(file_name):
            self.tree = etree.parse(file_name)
        else:
            print "No such file or directory: %s" % file_name
            sys.exit(1)

    def query_all_config_element(self):
        elements = etree.iterparse(self.file_name, events=('end',), tag='property')
        for events, element in elements:
            self.config_element[element.getchildren()[0].text] = element.getchildren()[1].text
        return self.config_element

    def get_value_by_name(self, query_name):
        elements = etree.iterparse(self.file_name, events=('end',), tag='property')
        for events, element in elements:
            if element.getchildren()[0].text == query_name:
                return 0, element.getchildren()[1].text

    def set_value_by_name(self, config_name, config_value, set_file):
        try:
            name_elements = self.tree.xpath("//property")
            for name in name_elements:
                if config_name == name.getchildren()[0].text:
                    name.getchildren()[1].text = config_value
            self.tree.write(set_file, pretty_print=True, encoding='UTF-8')

        except Exception, e:
            print e
            return 1


class LoadBalanceConfigParser(IcfsXmlParser):

    def __init__(self, file_name):
        IcfsXmlParser.__init__(self)
        self.file_name = file_name
        self.config_element = {}
        if os.path.exists(file_name):
            self.tree = etree.parse(file_name)
        else:
            print "No such file or directory: %s" % file_name
            sys.exit(1)

    def query_all_config_element(self):
        for element in self.tree.getroot().getchildren():
            if len(element):
                domain_config = {}
                time_config = {}
                address_config = {}
                for sub_element in element.getchildren():
                    if "time" == sub_element.tag:
                        time_config[sub_element.get("type")] = sub_element.get("value")
                    elif "serial" == sub_element.tag or "policy" == sub_element.tag:
                        domain_config[sub_element.tag] = sub_element.get("value")
                    elif "addresspool" == sub_element.tag:
                        address_config[sub_element.get("weight")] = sub_element.get("address")
                domain_config["time"] = time_config
                domain_config["addresspool"] = address_config
                self.config_element[element.get("name")] = domain_config
            else:
                self.config_element["port"] = element.get("receiver")
        return self.config_element

    def get_value_by_name(self, query_name):
        # because there maybe have the same name in different domain, so the query_name should in the format domain.*
        if "/" not in query_name and "port" == query_name:
            port_element = self.tree.xpath("//port[@receiver]")
            if port_element and 1 == len(port_element):
                return port_element[0].get("receiver")
            else:
                print "there have no port element with receiver attribute"
                return 1, None
        elif "/" in query_name:
            # The same name can be identify in different domain prefix
            domain_name = query_name.split("/")[0]
            domain_element = self.tree.xpath("//domainname[@name]")
            if domain_element:
                find_query_domain = [domain for domain in domain_element if domain.get("name") == domain_name]
                if find_query_domain:
                    if len(find_query_domain) != 1:
                        print "there have more than one domainname element with same name attribute"
                        return 1, None
                    else:
                        query_element_name = query_name.split("/")[1]
                        address_pool = {}
                        time_struct = {}
                        for sub_element in find_query_domain[0].getchildren():
                            if query_element_name == sub_element.tag:
                                if 1 == query_name.count("/"):
                                    if query_element_name == "addresspool":
                                        address_pool[sub_element.get("address")] = sub_element.get("weight")
                                    elif query_element_name == "time":
                                        time_struct[sub_element.get("type")] = sub_element.get("value")
                                    else:
                                        return 0, sub_element.get("value")
                                elif 2 == query_name.count("/"):
                                    # look for the final element
                                    if query_element_name == "time" and \
                                                    sub_element.get("type") == query_name.split("/")[2]:
                                        return 0, sub_element.get("value")
                                else:
                                    print "currently max support two dot"
                                    return 1, None
                        if 1 == query_name.count("/") and query_element_name == "addresspool":
                            return 0, address_pool
                        elif 1 == query_name.count("/") and query_element_name == "time":
                            return 0, time_struct
            else:
                print "there have no domainname element with name attribute"
                return 1, None
        else:
            print "Unknown query name %s, please check" % query_name
            return 1, None

    def set_value_by_name(self, config_name, config_value, set_file):
        if "/" not in config_name:
            # modify the port number
            if "port" == config_name:
                if not re.match(r"^[0-9]{1,5}$", config_value) or int(config_value) > 65535:
                    print "please check the config value type"
                    return 1
                port_element = self.tree.xpath("//port[@receiver]")
                if port_element and 1 == len(port_element):
                    port_element[0].set("receiver", config_value)
                else:
                    print "there have no port element with receiver attribute"
                    return 1
            # modify the domain name
            elif "domainname" == config_name:
                if not re.match(r"^(\w+.){2}\w+$", config_value):
                    print "please check the config value type"
                    return 1
                domain_element = self.tree.xpath("//domainname[@name]")
                if domain_element and 1 == len(domain_element):
                    domain_element[0].set("name", config_value)
                else:
                    print "there have no port element with receiver attribute"
                    return 1
            else:
                print "Unknown config element %s" % config_name

        elif "/" in config_name:
            domain_name = config_name.split("/")[0]
            domain_element = self.tree.xpath("//domainname[@name]")
            if domain_element:
                find_set_domain = [domain for domain in domain_element if domain.get("name") == domain_name]
                if find_set_domain:
                    if len(find_set_domain) != 1:
                        print "there have more than one domainname element with same name attribute"
                        return 1
                    else:
                        set_element_name = config_name.split("/")[1]
                        find_middle = False
                        find_end = False
                        for sub_element in find_set_domain[0].getchildren():
                            if set_element_name == sub_element.tag:
                                if 1 == config_name.count("/"):
                                    if set_element_name == "policy" and config_value not in ["round-robin", "link"]:
                                        print "incorrect config value, it should be round-robin or link"
                                        return 1
                                    sub_element.set("value", config_value)
                                elif 2 == config_name.count("/"):
                                    if set_element_name == "time" and \
                                                    sub_element.get("type") == config_name.split("/")[2]:
                                        sub_element.set("value", config_value)
                                        find_end = True
                                    elif set_element_name == "addresspool" and \
                                                             sub_element.get("weight") == config_name.split("/")[2]:
                                        ip_format(config_value)
                                        sub_element.set("address", config_value)
                                        find_end = True
                                else:
                                    print "currently max support two dot"
                                    return 1
                                find_middle = True
                        if not find_middle:
                            print "Unknown config name \\%s\\, please check" % set_element_name
                            return 1
                        if not find_end:
                            print "Unknown \\%s, please check" % config_name.split("/")[2]
                            return 1
                else:
                    print "unknown domain name %s", domain_name
                    return 1
            else:
                print "please check your set element %s" % config_name
                return 1
        self.tree.write(set_file, pretty_print=True, encoding='UTF-8')


class LinkConfigParser(IcfsXmlParser):

    def __init__(self, file_name):
        IcfsXmlParser.__init__(self)
        self.file_name = file_name
        self.config_element = {}
        if os.path.exists(file_name):
            self.tree = etree.parse(file_name)
        else:
            print "No such file or directory: %s" % file_name
            sys.exit(1)

    def query_all_config_element(self):
        interval_config = {}
        snmp_config = {}
        protocol_config = {}
        for element in self.tree.getroot().getchildren():
            if element.tag == "Interval":
                interval_config[element.get("name")] = element.text
            elif element.tag == "Snmp":
                for sub_element in element.getchildren():
                    snmp_config[sub_element.tag] = sub_element.text
            elif element.tag == "Protocol":
                port = []
                for child in element.getchildren():
                    port.append(child.text)
                protocol_config[element.get("name")] = port
            else:
                print "Unknown element %s" % element.tag
        self.config_element["Snmp"] = snmp_config
        self.config_element["Interval"] = interval_config
        self.config_element["Protocol"] = protocol_config

        return self.config_element

    def get_value_by_name(self, query_name):
        if "/" not in query_name or ("/" in query_name and not query_name.split("/")[1]):
            if "/" in query_name:
                query_name = query_name.split("/")[0]
            if query_name == "Protocol":
                protocol_config = {}
                protocol_elements = self.tree.xpath("//Protocol[@name]")
                if not protocol_elements:
                    print "Can't find protocol element"
                    return 1, None
                for protocol_element in protocol_elements:
                    port = []
                    for protocol_sub_element in protocol_element.getchildren():
                        port.append(protocol_sub_element.text)
                    protocol_config[protocol_element.get("name")] = port
                return 0, protocol_config
            elif query_name == "Interval":
                interval_config = {}
                interval_elements = self.tree.xpath("//Interval[@name]")
                if not interval_elements:
                    print "Can't find interval element"
                    return 1, None
                for interval_element in interval_elements:
                    interval_config[interval_element.get("name")] = interval_element.text
                return 0, interval_config
            elif query_name == "Snmp":
                snmp_config = {}
                snmp_elements = self.tree.xpath("//Snmp")
                if not snmp_elements:
                    print "Can't find snmp element"
                    return 1, None
                for snmp_element in snmp_elements:
                    for sub_element in snmp_element.getchildren():
                        snmp_config[sub_element.tag] = sub_element.text
                return 0, snmp_config
        elif query_name.count("/") == 1:
            parent_name = query_name.split("/")[0]
            children_name = query_name.split("/")[-1]
            if parent_name == "Interval":
                find_element = self.tree.xpath("//{0}[@name=\"{1}\"]".format(parent_name, children_name))
                if not find_element:
                    print "Can't find, please check the query name %s" % query_name
                    return 1, None
                elif len(find_element) == 1:
                    return 0, find_element[0].text
                else:
                    print "There have more than one %s, please check" % query_name
            elif parent_name == "Protocol":
                find_element = self.tree.xpath("//{0}[@name=\"{1}\"]".format(parent_name, children_name))
                if not find_element:
                    print "Can't find, please check the query name %s" % query_name
                    return 1, None
                elif len(find_element) == 1:
                    port = []
                    for sub_element in find_element[0].getchildren():
                        port.append(sub_element.text)
                    return 0, port
                else:
                    print "There have more than one %s, please check" % query_name
            elif parent_name == "Snmp":
                find_element = self.tree.xpath("//{0}/{1}".format(parent_name, children_name))
                if not find_element:
                    print "Can't find, please check the query name %s" % query_name
                    return 1, None
                elif len(find_element) == 1:
                    return 0, find_element[0].text
                else:
                    print "There have more than one %s, please check" % query_name
        else:
            print "currently onlu support one slash!"
            return 1, None

    def set_value_by_name(self, config_name, config_value, set_file):
        if "/" not in config_name or ("/" in config_name and not config_name.split("/")[1]):
            print "please specify the config name"
        elif config_name.count("/") == 1:
            parent_name = config_name.split("/")[0]
            children_name = config_name.split("/")[-1]
            if parent_name == "Interval":
                find_element = self.tree.xpath("//{0}[@name=\"{1}\"]".format(parent_name, children_name))
                if not find_element:
                    print "Can't find, please check the query name %s" % config_name
                    return 1
                elif len(find_element) == 1:
                    find_element[0].text = config_value
                else:
                    print "There have more than one %s, please check" % config_name
            elif parent_name == "Protocol":
                find_element = self.tree.xpath("//{0}[@name=\"{1}\"]".format(parent_name, children_name))
                if not find_element:
                    print "Can't find, please check the query name %s" % config_name
                    return 1
                elif len(find_element) == 1:
                    ports = config_value.split(".")
                    for port in ports:
                        if not re.match(r"^[0-9]{1,5}$", port) or int(port) > 65535:
                            print "the port %s is illegal" % port
                            return 1
                    # delete the original element
                    etree.strip_elements(find_element[0], "Port")
                    # add new element
                    count = 0
                    for port in ports:
                        count += 1
                        temp = etree.SubElement(find_element[0], "Port")
                        temp.text = port
                        if count != len(ports):
                            temp.tail = "\n    "
                        else:
                            temp.tail = "\n"
                else:
                    print "There have more than one %s, please check" % config_name
            elif parent_name == "Snmp":
                find_element = self.tree.xpath("//{0}/{1}".format(parent_name, children_name))
                if not find_element:
                    print "Can't find, please check the query name %s" % config_name
                    return 1
                elif len(find_element) == 1:
                    if children_name == "Version" and config_value != 2:
                        print "Currently only support SNMP version 2"
                        return 1
                    elif children_name == "Dst_ip":
                        ip_format(config_value)
                    elif children_name == "Dst_port" and \
                                          (not re.match(r"^[0-9]{1,5}$", config_value) or int(config_value) > 65535):
                        print "the port %s is illegal" % config_value
                        return 1
                    find_element[0].text = config_value
                else:
                    print "There have more than one %s, please check" % config_name
        else:
            print "currently onlu support one slash!"
            return 1
        self.tree.write(set_file, pretty_print=True, encoding='UTF-8')


class XmlConfigParserFactory:
    def __init__(self):
        pass

    @ classmethod
    def get_config_parser(cls, config_file):
        file_type = config_file.split("/")[-1]
        if "core-site.xml" == file_type or "mapred-site.xml" == file_type or "yarn-site.xml" == file_type:
            return HadoopXmlParser(config_file)
        elif "links.xml" == file_type:
            return LinkConfigParser(config_file)
        elif "loadbalance.xml" == file_type:
            return LoadBalanceConfigParser(config_file)
        else:
            print "unknown file type %s" % config_file
            sys.exit(1)


def query(query_mode, query_key, file_query):
    config_parser = XmlConfigParserFactory.get_config_parser(file_query)
    if "query_all" == query_mode and query_key is None:
        elements = config_parser.query_all_config_element()
        for element in elements:
            print "{0}: {1}".format(element, elements[element])
    elif "query_key" == query_mode and query_key:
        ret, return_value = config_parser.get_value_by_name(query_key)
        if not ret:
            print return_value
        else:
            sys.exit(1)


def update(set_key, set_value, set_file):
    config_parser = XmlConfigParserFactory.get_config_parser(set_file)
    ret = config_parser.set_value_by_name(set_key, set_value, set_file)
    if not ret:
        print "set success"


if __name__ == "__main__":
    mode = None
    key = None
    query_file = None
    value = None

    try:
        parser = OptParser()
        parser.append("help", "{-h|--help}")
        parser.append("query", "--query,--file=,{--all|--key=}")
        parser.append("update", "--update,--file=,--key=,--value=")

        m_name, m_opts = parser.parse(sys.argv[1:])
    except Exception, err:
        print err
        print "Error(610): Invalid input! "
        sys.exit(1)

    for x, y in m_opts:
        if '--all' == x:
            mode = "query_all"
        elif '--key' == x:
            mode = "query_key"
            key = y
        elif '--file' == x:
            query_file = y
        elif '--value' == x:
            value = y

    if m_name == 'help':
        usage()
    elif m_name == 'query':
        query(mode, key, query_file)
    elif m_name == 'update':
        update(key, value, query_file)
    else:
        print "Error(610): Invalid input! mode_name:%s" % m_name
