import os;


def _jsonrpc(value="error", **ka):
    base = {"jsonrpc": "2.0", value: None, "id": "id"};
    if ka:
        base[value] = ka;
    return base;
    
def get_filename(forms, files):
    if "name" in forms:
        return forms["name"];
    elif len(files) > 0:
        return files.file.filename;
    else:
        return None;


def save(forms, files, dest, identifier):
    filename = get_filename(forms, files);
    
    if filename is None:
        return _jsonrpc("error", code=102, message="Filename must be present");

    if "chunk" in forms and "chunks" in forms:
        chunk = int(forms["chunk"]);
        total = int(forms["chunks"]);
    else:
        chunk = 0;
        total = 1;

    first = chunk == 0;
    last = chunk == total - 1;

    try:
        destfile = os.path.join(dest, filename);
        if os.access(destfile, os.F_OK):
            return _jsonrpc("error", code=102, message="File already uploaded");

        tmpfile = os.path.join(dest, "{0}.part".format(filename));
        with open(tmpfile, "w+b" if first else "ab") as fd:
            files.file.save(fd);

        if last:
            os.rename(tmpfile, destfile);
            os.system("chmod +x " + destfile);
    except:
        return _jsonrpc("error", code=101, message="Failed to write file.");
    return _jsonrpc("result", identifier=identifier);