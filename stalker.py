import_ok = True

SCRIPT_NAME = "stalker"
SCRIPT_AUTHOR = "Auv"
SCRIPT_VERSION = "0.01"
SCRIPT_LICENSE = "GPL3"
SCRIPT_DESC = "A simple-to-use stalker script for WeeChat."

STALKER_CMD = "stalker"

STALKER_DIR_NAME = 'stalker'
STALKER_DB_NAME = 'stalker.db'
# Use a symbol not used in IRC.
CACHE_SEPARATOR = '^^'

try:
    import weechat as w
except:
    print('This script must be run under WeeChat.')
    print('Get WeeChat now at: http://www.weechat.org/')
    import_ok = False

try:
    import sqlite3
except:
    print('Missing module sqlite3 for plugin %s' % STALKER_CMD)
    import_ok = False

# Basic part of Python interpreter
import os
import traceback

hosts_cache = None

class Host(object):
    def __init__(self, id, server, hostname, *nicks):
        self.hostname = hostname
        self.server = server
        self.nicks = list(nicks)
        self.id = id

    def add_nick(self, nick):
        self.nicks.append(nick)

    def __repr__(self):
        return '(%s, %s, %s)' % (self.hostname, self.server, repr(self.nicks))

def stalker_init():
    w.mkdir_home(STALKER_DIR_NAME, 0755)

    global home
    home = w.info_get('weechat_dir', '')


def stalker_load_db():
    db_path = os.path.join(home, STALKER_DIR_NAME, STALKER_DB_NAME)
    db_new = False

    if not os.path.exists(db_path):
        db_new = True

    global conn
    # Either creates or loads DB.
    conn = sqlite3.connect(db_path)
    
    if db_new:
        cur = conn.cursor()
        cur.execute('CREATE TABLE hosts (id INTEGER PRIMARY KEY AUTOINCREMENT, server TEXT,'
                    ' host TEXT)')
        cur.execute('CREATE TABLE nicks'
                    ' (id INTEGER PRIMARY KEY AUTOINCREMENT, host_id INTEGER NOT NULL,'
                    ' nick TEXT)')
        conn.commit()
        cur.close()

def read_hosts():
    cur = conn.cursor()
    cur.execute('SELECT * FROM hosts')

    global hosts_cache

    hosts_cache = {}
    rows = cur.fetchall()
    
    for row in rows:
        nick_cur = conn.cursor()
        nick_cur.execute('SELECT nick from nicks WHERE host_id = %d' % row[0])
        
        nicks = [r[0] for r in nick_cur.fetchall()]

        hosts_cache[row[1] + CACHE_SEPARATOR + row[2]] = Host(row[0], row[1], row[2], *nicks)
        nick_cur.close()

    cur.close()

def add_data(server, hostname, nick):
    if not hosts_cache:
        read_hosts()

    if (server + CACHE_SEPARATOR + hostname) in hosts_cache:
        host = hosts_cache[server + CACHE_SEPARATOR + hostname]
        cur = conn.cursor()
        if nick not in host.nicks:
            cur.execute('INSERT INTO nicks (host_id, nick) VALUES ( "%s", "%s" )' % (host.id, nick))
            host.add_nick(nick)
        conn.commit()
        cur.close()
    else:
        cur = conn.cursor()
        cur.execute('INSERT INTO hosts (server, host) VALUES ( "%s", "%s" )' % (server, hostname))
        hosts_cache[server + CACHE_SEPARATOR + hostname] = Host(cur.lastrowid, server, hostname, nick)
        cur.execute('INSERT INTO nicks (host_id, nick) VALUES ( "%s", "%s" )' % (cur.lastrowid, nick))
        conn.commit()
        cur.close()

def stalk_cb(data, signal, signal_data):
    hostmask = signal_data.split(' ')[0]
    hostname = hostmask.split('@')[1]
    server = signal.split(',')[0]
    nick = w.info_get('irc_nick_from_host', hostmask)

    w.prnt('', "Stalking user %s with hostname %s" % (nick, hostname))

    add_data(server, hostname, nick)

    return w.WEECHAT_RC_OK

## The bottom half of the stalker command. Does the real work.
def stalker_cmd_bottom(buffer, server, hostname):
    if not hosts_cache:
        read_hosts()
    
    if hostname in hosts_cache:
        w.prnt(buffer, 'Nicknames: %s' % repr(hosts[hostname].nicks))
        return w.WEECHAT_RC_OK
    else:
        w.prnt(buffer, 'Could not find username.')
        return w.WEECHAT_RC_ERROR

# Data is buffer
def stalker_cmd_cb(data, signal, hashtable):
    if hashtable['error'].strip():
        return w.WEECHAT_RC_ERROR

    # Look for a code 352
    line = next(s for s in hashtable['output'].split('\n') if s.split()[1] == '352')
    w.prnt(data, line)
    if not line:
        return w.WEECHAT_RC_EAT_OK
    server = w.buffer_get_string(data, "localvar_server")
    hostname = line.split()[5]

    

    return stalker_cmd_bottom(data, server, hostname)

def stalker_cmd(data, buffer, args):
    args = args.strip()
    if ' ' in args:
        return w.WEECHAT_RC_ERROR

    server = w.buffer_get_string(buffer, "localvar_server")

    # it's a hostname
    if '@' in args:
        stalker_cmd_bottom(buffer, server, args.split('@')[-1])
    else:
        w.hook_hsignal ("irc_redirection_stalker_who", "stalker_cmd_cb", buffer)
        w.hook_hsignal_send("irc_redirect_command",
                                  { "server": server, "pattern": "who", "signal": "stalker" })
        w.hook_signal_send("irc_input_send", w.WEECHAT_HOOK_SIGNAL_STRING,
                                 ("%s;;2;;/who %s") % (server, args))
        
    return w.WEECHAT_RC_OK


def stalker_finish():
    global conn
    if conn:
        conn.close()

if __name__ == '__main__' and import_ok:
    if w.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION,
                        SCRIPT_LICENSE, SCRIPT_DESC, "", ""):
        stalker_init()
        try:
            stalker_load_db()
        except:
            traceback.print_exc()
            w.prnt('', '%s could not load database. Unloading script.' % SCRIPT_NAME)
            # Commit honourable script-icide
            w.hook_signal_send('python_script_remove',
                                     w.WEECHAT_HOOK_SIGNAL_STRING,
                                     os.path.basename(__file__))

        w.hook_command(STALKER_CMD, SCRIPT_DESC,
                      "<user>",
                      '''
                         user: User or hostname to stalk!
                      ''',
                      '%(irc_channel_nicks_hosts)',
                      'stalker_cmd', 'stalker_finish')
        w.hook_signal("*,irc_in2_join", "stalk_cb", "")
        w.hook_signal("*,irc_in2_part", "stalk_cb", "")
