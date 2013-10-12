#!/usr/bin/python

import os, sys, struct, optparse, StringIO, ConfigParser

make_option = optparse.make_option

defines = {}
def add_var(option, opt, value, parser):
    var, val = value.split('=')
    defines[var] = val

opt = optparse.OptionParser(option_list = [
        make_option('-o',
                    dest = 'output',
                    help = 'write to FILE',
                    metavar = 'FILE'),
        make_option('-d',
                    dest = 'depends',
                    help = 'write dependencies to FILE',
                    metavar = 'FILE',
                    default = None),
        make_option('-m',
                    dest = 'manifest',
                    help = 'read manifest from FILE',
                    metavar = 'FILE'),
        make_option('-D',
                    type = 'string',
                    help = 'define VAR=DATA',
                    metavar = 'VAR=DATA',
                    action = 'callback',
                    callback = add_var),
        make_option('-s',
                    dest = 'offset',
                    help = 'offset to write the data to',
                    metavar = 'OFFSET',
                    default = 0),
        make_option('-v',
                    action = 'store_true',
                    dest = 'verbose',
                    help = 'show verbose output',
                    default = False),	

])

(options, args) = opt.parse_args()

def syscmd(cmd):
    if options.verbose == True:
        print 'INFO %s' % cmd
    os.system(cmd)


depends = StringIO.StringIO()
if options.depends:
    depends = file(options.depends, 'w')
#out = file(options.output, 'w')
manifest = ConfigParser.SafeConfigParser()
manifest.optionxform = str # avoid lowercasing
manifest.read(options.manifest)

depends.write('%s: \\\n' % (options.output,))


zfs_root='/zfs'
loop_dev='/dev/loop7'
dev='/dev/vblk0.1'
zfs_pool='osv'
zfs_fs='usr'

if os.path.exists(zfs_root) and os.listdir(zfs_root): 
    print 'Please make sure %s does not exist or is an empty directory' % zfs_root
    sys.exit(1)

syscmd('mkdir -p %s' % zfs_root)

syscmd('rm -f %s' % options.output)
syscmd('truncate --size 10g %s' % options.output)
syscmd('losetup -o %s %s %s' % (options.offset, loop_dev, options.output))

syscmd('ln %s %s' % (loop_dev, dev))

syscmd('zpool create -f %s -R %s %s' % (zfs_pool, zfs_root, dev))
syscmd('zfs create %s/%s' % (zfs_pool, zfs_fs))

files = dict([(f, manifest.get('manifest', f, vars = defines))
              for f in manifest.options('manifest')])

def expand(items):
    for name, hostname in items:
        if name.endswith('/**') and hostname.endswith('/**'):
            name = name[:-2]
            hostname = hostname[:-2]
            for dirpath, dirnames, filenames in os.walk(hostname):
                for filename in filenames:
                    relpath = dirpath[len(hostname):]
                    if relpath != "" :
                        relpath += "/"
                    yield (name + relpath + filename,
                           hostname + relpath + filename)
        elif '/&/' in name and hostname.endswith('/&'):
            prefix, suffix = name.split('/&/', 1)
            yield (prefix + '/' + suffix, hostname[:-1] + suffix)
        else:
            yield (name, hostname)

def unsymlink(f):
    try:
        link = os.readlink(f)
        if link.startswith('/'):
            # try to find a match
            base = os.path.dirname(f)
            while not os.path.exists(base + link):
                base = os.path.dirname(base)
        else:
            base = os.path.dirname(f) + '/'
        return unsymlink(base + link)
    except Exception:
        return f

files = list(expand(files.items()))
files = [(x, unsymlink(y)) for (x, y) in files]

for name, hostname in files:
    depends.write('\t%s \\\n' % (hostname,))
    if name[:4] in [ '/usr' ]:
        syscmd('mkdir -p %s/`dirname %s`' % ('/zfs/', name))
        syscmd('cp -L %s %s/%s' % (hostname, '/zfs/', name))

syscmd('zpool export %s' % zfs_pool)
syscmd('sleep 2')
syscmd('losetup -d %s' % loop_dev)
syscmd('rm %s' % dev)

syscmd('chmod g+w %s' % options.output)
syscmd('chmod o+w %s' % options.output)

depends.write('\n\n')
depends.close()
