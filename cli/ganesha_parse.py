#!/usr/bin/python
# -*- copyright -*-
#coding:utf-8

import sys
import re
import StringIO

INDENT_WIDTH = 4

class StringElement(object):
    def __init__(self, s):
        if isinstance(s, str):
            self._value = s
        else:
            raise ValueError("StringElement can only hold str type value")
    
    def getValue(self):
        return self._value;
    
    def setValue(self, s):
        if isinstance(s, str):
            self._value = s
        else:
            raise ValueError("StringElement can only hold str type value")

class ListElement(object):
    def __init__(self, l = []):
        self._list = []
        self._iterator = iter(self._list)
    
    def __iter__(self):
        self._iterator = iter(self._list)
        return self
    
    def next(self):
        return self._iterator.next()
        
    def group(self, k):
        """L.group(key) -- return all value of key as a list"""
        return [value for key,value in self._list if key == k]
    
    def append(self, k, v):
        """L.append(key, value) -- append key-value pair to list"""
        if isinstance(v, StringElement) or isinstance(v, ListElement):
            self._list.append([k, v])
        else:
            raise ValueError("ListElement can only hold StringElement or ListElement")
    
    def remove_key(self, k):
        """L.remove_key(key) -- remove all key occurrences"""
        self._list = [i for i in self._list if i[0] != k]
    
    def remove_key_value(self, k, v):
        """L.remove_key_value(key, value) -- remove all key-value occurrences"""
        self._list = [i for i in self._list if i[0] != k or i[1] != v]
    
    def has_key(self, k):
        """L.has_key(key) -- return True if key in list, otherwise return False"""
        for key,value in self._list:
            if key == k:
                return True
        return False
    
    def get_string_value(self, k):
        """L.get(key) -- return first occurrence of key"""
        if not isinstance(k, str):
            raise TypeError("TypeError: expected a string object")
        
        for key, value in self._list:
            if key == k and isinstance(value, StringElement):
                return value.getValue()
        return None
    
    def set_string_value(self, k, v):
        """L.set(key,value) -- set first occurrence of key to value, append new key-value if key does not exist"""
        if not isinstance(k, str) or not isinstance(v, str):
            raise TypeError("TypeError: expected a string object")
        
        for key, value in self._list:
            if key == k and isinstance(value, StringElement):
                value.setValue(v)
                return None
                
        self._list.append([k, StringElement(v)])
        

def _parse_list(s):
    # define enum STATE
    STATE_NONE = 0          # none state
    STATE_NOTE = 1          # note state
    STATE_KEY = 2           # key state
    STATE_VALUE = 3         # value state
    STATE_LIST = 4          # list state
    
    value_list = ListElement()
    state = STATE_NONE
    key = ""
    value = ""
    
    front_brace_cnt = 0
    back_brace_cnt = 0
    
    # state machine
    for c in s:
        if state == STATE_NONE:
            if c in (" ", "\t", "\r", "\n"):
                continue
            elif c in ("{", "}", "=", ";"):
                raise SyntaxError("invalid format: key start with '{', '}', '=', ';'")
            elif c == "#":
                state = STATE_NOTE
            else:
                state = STATE_KEY
                key = c
        elif state == STATE_NOTE:
            if c != "\n":
                continue
            else:
                state = STATE_NONE
        elif state == STATE_KEY:
            if c == "=":
                key = key.strip()
                if "\n" in key:
                    print key
                    raise SyntaxError("invalid format: line break in key")
                state = STATE_VALUE
            elif c == "{":
                key = key.strip()
                state = STATE_LIST
            elif c in ("}", ";"):
                raise SyntaxError("invalid format: key end with '}', ';'")
            else:
                key = key + c
        elif state == STATE_VALUE:
            if c in ("{", "}", "=", "#"):
                raise SyntaxError("invalid format: value start with '{', '}', '=', '#'")
            elif c == ";":
                value = value.strip()
                if "\n" in value:
                    raise SyntaxError("invalid format: line break in value")
                value_list.append(key, StringElement(value))
                state = STATE_NONE
                key = ""
                value = ""
            else:
                value = value + c
        elif state == STATE_LIST:
            if c == "{":
                front_brace_cnt += 1
                value = value + c
            elif c == "}":
                if front_brace_cnt == back_brace_cnt:
                    value_list.append(key, _parse_list(value))
                    state = STATE_NONE
                    key = ""
                    value = ""
                else:
                    back_brace_cnt += 1
                    value = value + c
            else:
                value = value + c
        else:
            raise SyntaxError("invalid state")

    # there's an error if state is neither STATE_NONE nor STATE_NOTE at last
    if state not in (STATE_NONE, STATE_NOTE):
        raise SyntaxError("invalid format: end state error %d"%state)

    return value_list
    
def _dump_list(value_list, indent=0):
    s = StringIO.StringIO()
    if not isinstance(value_list, ListElement):
        raise ValueError("Input is not ListElement")
        
    for key, element in value_list:
        if isinstance(element, ListElement):
            s.write(" " * indent * INDENT_WIDTH + key + " {\n")
            s.write(_dump_list(element, indent+1))
            s.write(" " * indent * INDENT_WIDTH + "}\n")
        elif isinstance(element, StringElement):
            s.write(" " * indent * INDENT_WIDTH + key + " = " + element.getValue() + ";\n")
        else:
            raise ValueError("invalid Key-Value pair")
            
    return s.getvalue()

def parse_file(filename):
    # read file content
    content = ""
    with open(filename, "r") as fp:
        content = fp.read()
    
    # remove note
    # pattern = re.compile("#.*?(\n|$)")
    # content = pattern.sub("", content)
    
    # remove white space
    # content = content.strip()
    # pattern = re.compile(r"\s*(\{|\}|=|;)\s*")
    # content = pattern.sub(r"\1", content)
    
    root = _parse_list(content)
    return root
    
def dump_file(filename, value_list):
    content = _dump_list(value_list)
    with open(filename, "w") as fp:
        fp.write(content)

if __name__ == "__main__":
    try:
        root = parse_file("E:/parse/ganesha.conf1")
    except (IOError, SyntaxError), e:
        print e
        sys.exit(1)
        
    # add
    # delete
    # modify
    # get
    
    try:
        dump_file("E:/parse/ganesha.conf.bak", root)
    except (ValueError, IOError), e:
        print e
        sys.exit(1)
    