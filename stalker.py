import_ok = True

SCRIPT_NAME = "stalker"
SCRIPT_AUTHOR = "JackMc"
SCRIPT_VERSION = "0.01"
SCRIPT_LICENSE = "GPL3"
SCRIPT_DESC = "A simple-to-use stalker script for WeeChat."

STALKER_CMD = "stalker"

STALKER_DIR_NAME = 'stalker'
STALKER_DB_NAME = 'stalker.db'

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

who_cache = {}

def who_cache_update(nick, server, hostname):
    global who_cache
    who_cache[nick + server] = hostname

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

def add_data(server, hostname, nick):
    sel_cur = conn.cursor()
    sel_cur.execute('SELECT id FROM hosts WHERE server = "%s" and host = "%s"' % (server, hostname))
    rows = sel_cur.fetchall()
    count = len(rows)

    if count:
        # Get the id of the host we're associated with
        id = rows[0][0]

        nick_checkcur = conn.cursor()
        nick_checkcur.execute('SELECT COUNT(*) FROM nicks WHERE host_id = %d AND nick = "%s"' % (id, nick))
        
        cur = conn.cursor()
        if not nick_checkcur.fetchone()[0]:
            cur.execute('INSERT INTO nicks (host_id, nick) VALUES ( "%s", "%s" )' % (id, nick))
        conn.commit()
        cur.close()
        nick_checkcur.close()
    else:
        cur = conn.cursor()
        cur.execute('INSERT INTO hosts (server, host) VALUES ( "%s", "%s" )' % (server, hostname))
        cur.execute('INSERT INTO nicks (host_id, nick) VALUES ( "%s", "%s" )' % (cur.lastrowid, nick))
        conn.commit()
        cur.close()
    
    sel_cur.close()

def stalk_nick_cb(data, signal, signal_data):
    split = signal_data.split(' ')
    newnick = split[2][1:] if split[2].startswith(':') else split[2]
    oldnick = w.info_get('irc_nick_from_host', split[0])
    server = signal.split(',')[0]

    if (oldnick + server) in who_cache:
        add_data(server, who_cache[oldnick + server], newnick)
    else:
        add_data(server, split[0].split('@')[-1], newnick)
    return stalk_cb(data, signal, signal_data)

def stalk_quit_cb(data, signal, signal_data):
    server = signal.split(',')[0]
    hostname = signal_data.split(' ')[0].split('@')[-1]
    nick = w.info_get('irc_nick_from_host', signal_data.split(' ')[0])
    global who_cache

    if (nick + server) in who_cache:
        del who_cache[nick + server]

    val = stalk_cb(data, signal, signal_data)

    return val
    

def stalk_cb(data, signal, signal_data):
    hostmask = signal_data.split(' ')[0]
    hostname = hostmask.split('@')[1]
    server = signal.split(',')[0]
    nick = w.info_get('irc_nick_from_host', hostmask)
    if (nick + server) not in who_cache:
        who_cache_update(nick, server, hostname)
        add_data(server, hostname, nick)

    return w.WEECHAT_RC_OK

## The bottom half of the stalker command. Does the real work.
def stalker_cmd_bottom(buffer, server, hostnames):
    cur = conn.cursor()
    rows = []

    for hostname in hostnames:
        cur.execute(('SELECT nicks.nick FROM nicks, hosts'
                     ' WHERE hosts.server = "%s" AND hosts.host = "%s"'
                     ' AND nicks.host_id = hosts.id') % (server, hostname))

        rows += cur.fetchall()

    if len(rows):
        w.prnt(buffer, 'Nicknames: %s' % ', '.join([r[0] for r in rows]))
        return w.WEECHAT_RC_OK_EAT
    else:
        w.prnt(buffer, 'Could not find username.')
        return w.WEECHAT_RC_ERROR

# Data is buffer
def stalker_cmd_cb(data, signal, hashtable):
    if hashtable['error'].strip():
        return w.WEECHAT_RC_ERROR

    # Look for a code 352
    try:
        line = next(s for s in hashtable['output'].split('\n') if s.split()[1] == '352')
    except:
        return w.WEECHAT_RC_OK_EAT

    if not line:
        return w.WEECHAT_RC_OK_EAT
    split = line.split()
    nick = split[4]
    server = w.buffer_get_string(data, "localvar_server")
    hostname = split[5]
    who_cache_update(nick, server, hostname)

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
        # Check if the user's in our database already.
        cur = conn.cursor()
        cur.execute('SELECT host_id FROM nicks WHERE nick = "%s"' % (args))
        rows = cur.fetchall()
        cur.close()

        if len(rows):
            host_id = rows[0][0]
            cur = conn.cursor()
            cur.execute('SELECT host FROM hosts WHERE id = %d' % host_id)
            hostnames = [c[0] for c in cur.fetchall()]
            for hostname in hostnames:
                who_cache_update(args, server, hostname)
            stalker_cmd_bottom(buffer, server, hostnames)
            cur.close()
        else:
            if (args + server) in who_cache:
                stalker_cmd_bottom(buffer, server, who_cache[args + server])
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
        except Exception as e:
            traceback.print_exc()
            w.prnt('', '%s could not load database: %s. Unloading script.' % (SCRIPT_NAME, str(e)))
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
        w.hook_signal("*,irc_in2_quit", "stalk_quit_cb", "")
        w.hook_signal("*,irc_in2_nick", "stalk_nick_cb", "")
        w.hook_signal("*,irc_in2_privmsg", "stalk_cb", "")
