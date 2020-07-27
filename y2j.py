from oyaml import load, dump

try:
    from oyaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from oyaml import Loader, Dumper

import json
import sys
import argparse
import os
from os import listdir, getcwd
from os.path import isfile, join, isdir
import re


def beautify_avro(_s):
    pat = r'{[^{]*?}'
    for m in re.finditer(pat, _s):
        _x = m.group(0)
        _x = _x.replace("\n", "").replace("  ", "").replace(",", ", ").replace("\t", "")
        _s = re.sub(escapeRegExp(m[0]), _x, _s)
    return _s


def json2jsonl(_s):
    _s = _s.replace("\n", "").replace("  ", "").replace(",", ", ").replace("\t", "")
    return _s


def convert(_file, _outputfile, _json):
    with open(_file, "r") as f:
        if _json:
            # json to yaml conversion
            if _file.split('.')[1] == 'jsonl':
                lines = f.readlines()
                if os.path.exists(_outputfile):
                    os.remove(_outputfile)
                i = 1
                for line in lines:
                    data = json.loads(line)
                    obj = {f'@line{i}': data}
                    i += 1
                    if _outputfile:
                        with open(_outputfile, "a") as o:
                            dump(obj, o, Dumper=Dumper, default_flow_style=False)
                            o.write("\n")
                    else:
                        print(dump(obj, Dumper=Dumper, default_flow_style=False))
                with open(_outputfile, "a") as o:
                    o.write("'@end'")
            else:
                data = json.load(f)
                if _outputfile:
                    with open(_outputfile, "w") as o:
                        dump(data, o, Dumper=Dumper, default_flow_style=False)
                else:
                    print(dump(data, Dumper=Dumper, default_flow_style=False))

        else:
            # yaml to json conversion
            # detect avro schema
            body = f.read()
            if 'name:' in body and 'type: record' in body and 'fields' in body:
                _outputfile = _outputfile.split('.')[0] + '.avsc'

            # detect meta @line for generating jsonl instead of json
            if '@line' in body and '@end' in body:
                _outputfile += 'l'
                if os.path.exists(_outputfile):
                    os.remove(_outputfile)
                pat = r"@line.*?\n(.*?)\n'"
                for m in re.finditer(pat, body, re.DOTALL):
                    x = m[0]
                    if m[1]:
                        data = load(m[1], Loader=Loader)
                        if _outputfile:
                            json.dump(data, open(_outputfile, "a"))
                            with open(_outputfile, "a") as o:
                                o.write('\n')
                        else:
                            print(json.dumps(data))
            else:
                data = load(body, Loader=Loader)
                if _outputfile:
                    with open(_outputfile, "w") as o:
                        s = json.dumps(data, indent=4)
                        s = beautify_avro(s)
                        o.write(s)
                else:
                    print(json.dumps(data, indent=4))


def escapeRegExp(s):
    """
    This function escapes special characters in the str argument used in regular expressions
    and returns the modified string

    @param s: string
    @return: string
    """
    _s = re.sub(r'([-/\\^$*+?.()|[\]{}])', r'\\\1', s, 0)
    return _s


def cname(data):
    # if 'namespace' in data:
    #    _classname = data['namespace']
    # el
    if 'name' in data:
        _classname = data['name']
    else:
        _classname = 'unknown'
    return _classname


def to_uml(data):
    """
    this routine converts an AVRO json file (as an object) to Plantuml code
    @param data: AVRO data object
    @return: Plantuml code
    """

    classname = ''
    try:
        # use the name space field or by default the name
        # as class name
        classname = cname(data)

        # declare the class
        uml = 'class ' + classname + ' {\n'
        uml2 = {}
        if 'doc' in data:
            d = "\t/' " + data['doc'] + " '/\n"
        else:
            d = '\n'
        # if of record type, add fields name as class field
        if data['type'] == 'record':
            for f in data['fields']:
                key = cname(f['type'])
                uml += '\t+' + f['name'] + ': '
                if 'doc' in f:
                    doc = "\t/' " + f['doc'] + " '/\n"
                else:
                    doc = '\n'
                # look for depending objects if AVRO type is complex
                if type(f['type']) is dict:

                    t = f['type']['type']
                    if 'doc' in f['type']:
                        ddoc = "\t/' " + f['type']['doc'] + " '/\n"
                    else:
                        ddoc = '\n'
                    # get the complex type (enum, array, map, record)
                    if type(t) is not dict:

                        if t == 'enum' or t == 'record':
                            uml += t + ddoc
                            u = to_uml(f['type'])
                            uml2[key] = u, t

                        elif t == 'array':
                            # array has items
                            i = f['type']['items']
                            if type(i) is dict:
                                uml += t + ddoc
                                u = to_uml(i)
                                uml2[key] = u, t
                            elif type(i) is list:
                                uml += t[0] + ' | null ' + ddoc
                            else:
                                uml += t + ' of ' + i + ddoc

                        elif t == 'map':
                            # array has values
                            i = f['type']['values']
                            if type(i) is dict:
                                uml += t + ddoc
                                u = to_uml(i)
                                uml2[key] = u, t
                            elif type(i) is list:
                                uml += t[0] + ' | null ' + ddoc
                            else:
                                uml += t + ' of ' + i + ddoc

                        else:
                            uml += t + doc

                    else:
                        # need to dig into that :-)
                        uml += 'object' + doc

                # optional field or null
                elif type(f['type']) is list:
                    uml += f['type'][0] + ' | null ' + doc
                # mandatory field
                else:
                    uml += f['type'] + doc

        elif data['type'] == 'enum':
            for f in data['symbols']:
                uml += '\t+' + f + d

        uml += '}\n'

        for k in uml2:
            u, t = uml2[k]
            uml += '\n' + u
            if t in ['enum', 'record']:
                uml += classname + ' -- ' + k + '\n'
            else:
                uml += classname + ' --|{ ' + k + '\n'
        return uml

    except KeyError as e:
        print(classname + ': Malformed AVRO file - missing key: ' + str(e))
        return ''


def avro_uml(file):
    ext = file.split('.')[1]
    fpath = file[:-len(os.path.basename(file))]
    if ext == 'avsc':
        try:
            with open(file, 'r') as f:
                data = json.load(f)
            doc = '\n@startuml\nhide circle\nhide methods\nskinparam linetype ortho\n\n' + to_uml(
                data) + '\n@enduml\n'
            return doc
        except IOError:
            return ''
    elif ext == 'puml':
        try:
            with open(file, 'r') as f:
                data = f.read()
            # process include files in the .puml file
            pat = r'\!include (.*?)'
            for m in re.finditer(pat, data):
                ifile = os.path.join(fpath, m[1])
                with open(ifile, 'r') as f:
                    idata = f.read()
                data = re.sub(escapeRegExp(m[0]), "' Include " + m[1] + '\n' + idata, data)
            # remove any directive from file
            data = re.sub(r'@.*', '', data)
            data = re.sub(r'skinparam.*', '', data)
            data = re.sub(r'hide .*', '', data)

            doc = '\n{plantuml}\n@startuml\nhide circle\nskinparam linetype ortho\n' + data + '\n@enduml\n{plantuml}\n'
            return doc
        except IOError:
            return ''
    return ''


def main():
    parser = argparse.ArgumentParser("Convert yaml to json & vice-versa")

    parser.add_argument("-j", "--json", required=False, action='store_true',
                        help="convert json to yaml file")
    parser.add_argument("-l", "--jsonl", required=False, action='store_true',
                        help="convert json to jsonl file")
    parser.add_argument("-a", "--avro", required=False, action='store_true',
                        help="convert yaml to avro file")
    parser.add_argument("-u", "--uml", required=False, action='store_true',
                        help="convert avsc to puml file")
    parser.add_argument("-o", "--outputFile", required=False,
                        help="specify output file")
    parser.add_argument("-d", "--directory", required=False,
                        help="convert all files from ")
    parser.add_argument('file', nargs='?',
                        help="convert the specified file")
    args = parser.parse_args()

    if args.file is None and args.directory is None:
        print("Missing input file or directory")
        parser.print_help(sys.stderr)
        sys.exit(-1)

    if args.file:
        if '.' in args.file:
            ext = args.file.split('.')[1]
        else:
            ext = ''

        if args.jsonl and ext == 'json':
            if not args.outputFile:
                args.outputFile = join(args.file.split('.')[0] + '.jsonl')
            with open(args.file, 'r') as f:
                data = json2jsonl(f.read())
            with open(args.outputFile, "w") as f:
                f.write(data)
            sys.exit(0)
        elif args.jsonl and ext == 'jsonl':
            if not args.outputFile:
                args.outputFile = join(args.file.split('.')[0] + '.json')
            data = json.load(open(args.file, 'r'))
            json.dump(data, open(args.outputFile, 'w'), indent=4)
            sys.exit(1)

        if ext == 'json' or ext == 'avsc' or ext == 'jsonl':
            args.json = True
            if not args.outputFile:
                args.outputFile = join(args.file.split('.')[0] + '.yaml')
            if ext == '.avsc' and args.uml:
                data = avro_uml(args.file)
                with open(join(args.file.split('.')[0] + '.puml'), 'w') as f:
                    f.write(data)

        else:
            if not args.outputFile:
                if args.avro:
                    args.outputFile = join(args.file.split('.')[0] + '.avsc')
                else:
                    args.outputFile = join(args.file.split('.')[0] + '.json')

        convert(args.file, args.outputFile, args.json)

    elif args.directory:
        if args.directory == '.':
            args.directory = getcwd()
        if not isdir(args.directory):
            print("Invalid directory")
            sys.exit(-1)

        files = [f for f in listdir(args.directory) if isfile(join(args.directory, f))]
        for f in files:
            if '.' in f:
                ext = f.split('.')[1]
            else:
                ext = ''
            if args.json:
                if ext == 'json' or ext == 'avsc':
                    o = join(args.directory, f.split('.')[0] + '.yaml')
                    convert(join(args.directory, f), o, True)

            elif ext == 'yml' or ext == 'yaml':
                if args.avro:
                    o = join(args.directory, f.split('.')[0] + '.avsc')
                else:
                    o = join(args.directory, f.split('.')[0] + '.json')
                convert(join(args.directory, f), o, False)
        sys.exit(0)


if __name__ == "__main__":
    main()
