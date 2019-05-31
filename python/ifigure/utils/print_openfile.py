import builtins
openfiles = set()
oldfile = builtins.file
class newfile(oldfile):
    def __init__(self, *args):
        self.x = args[0]
        print(("### OPENING %s ###" % str(self.x)))            
        oldfile.__init__(self, *args)
        openfiles.add(self)

    def close(self):
        print(("### CLOSING %s ###" % str(self.x)))
        oldfile.close(self)
        openfiles.remove(self)
oldopen = builtins.open
def newopen(*args):
    return newfile(*args)
builtins.file = newfile
builtins.open = newopen

def printOpenFiles():
    print(("### %d OPEN FILES: [%s]" % (len(openfiles), ", ".join(f.x for f in openfiles))))
