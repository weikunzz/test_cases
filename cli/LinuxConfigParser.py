#!/usr/bin/python
#coding:utf-8
# -*- copyright -*-

# change log
# 20170104 shaoning (read) Bug fix(5449):clear current config before read

import sys
import re

class LinuxConfigParser():
    def __init__(self):
        self._list = []
        self._pattern = re.compile(r"^\s*([^#]*?)\s*?=\s*([^#]*?)\s*(?:#.*)?$")
    
    def items(self):
        return [(k,v) for t,k,v in self._list if t == 0]
    
    def keys(self):
        return [k for t,k,v in self._list if t == 0]
    
    def has_key(self, key):
        for t,k,v in self._list:
            if k == key:
                return True
        
        return False
    
    def get(self, key):
        for t,k,v in self._list:
            if k == key:
                return v
        
        return None
    
    def set(self, key, value):
        has_key = False
        for item in self._list:
            if item[0] == 0 and item[1] == key:
                item[2] = value
                has_key = True
                break
        
        if not has_key:
            self._list.append([0, key, value])
    
    def remove(self, key):
        self._list = [i for i in self._list if i[0] != 0 or i[1] != key]
    
    def read(self, filename):
        # clear current config
        self._list = []
        # read file content
        lines = []
        try:
            with open(filename, "r") as fp:
                lines = fp.readlines()
        except IOError, e:
            return False
        
        for line in lines:
            m = self._pattern.match(line)
            if m == None:
                self._list.append([1, "", line.strip()])
            else:
                self._list.append([0, m.group(1), m.group(2)])
        
        return True
    
    def write(self, filename):
        lines = []
        for x in self._list:
            if x[0] == 0:
                lines.append("%s=%s"%(x[1], x[2]))
            else:
                lines.append(x[2])
        
        content = "\n".join(lines)
        try:
            with open(filename, "w") as fp:
                fp.write(content)
        except IOError, e:
            return False
        
        return True


if __name__ == "__main__":
    parser = LinuxConfigParser()
    if not parser.read("D:/a.conf"):
        print "read failed"
        sys.exit(1)
    
    print "items:"
    print parser.items()
    print "keys"
    print parser.keys()
    
    print "get('a'):", parser.get("a")
    parser.set("c", "3")
    parser.remove("b")
    
    if not parser.write("D:/a.conf1"):
        print "write failed"
        sys.exit(1)
