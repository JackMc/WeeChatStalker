import_ok = True

SCRIPT_NAME = "stalker"
SCRIPT_AUTHOR = "Auv"
SCRIPT_VERSION = "0.01"
SCRIPT_LICENSE = "GPL3"
SCRIPT_DESC = "A simple-to-use stalker script for WeeChat."

STALKER_CMD = "stalker"

STALKER_DB_NAME = 'stalker.db'

try:
    import weechat as w
except:
    print('This script must be run under WeeChat.')
    print('Get WeeChat now at: http://www.weechat.org/')
    import_ok = True

try:
    import sqlite3
except:
    print('Missing module sqlite3 for plugin %s' % STALKER_CMD)
    import_ok = False

# Basic part of Python interpreter
import os

def stalker_init():
    w.mkdir_home('stalker', 0755)

    global home
    home = w.info_get('weechat_dir', '')


def stalker_load_db():
    db_path = os.path.join(home, STALKER_DB_NAME)
    db_new = False

    if not os.path.exists(db_path):
        db_new = True

    global conn
    # Either creates or loads DB.
    conn = sqlite3.connect(os.path.join(home, STALKER_DB_NAME))

    if db_new:
        cur = conn.cursor()
        cur.execute('CREATE TABLE hosts (id INTEGER PRIMARY KEY AUTOINCREMENT, host TEXT)');
        cur.execute('CREATE TABLE nicks'
                    ' (id INTEGER PRIMARY KEY AUTOINCREMENT, host_id INTEGER NOT NULL,'
                    ' nick TEXT)')
        conn.commit()
        cur.close()

def stalker_cmd(data, buffer, args):

    return w.WEECHAT_RC_OK

if __name__ == '__main__' and import_ok:
    if w.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION,
                        SCRIPT_LICENSE, SCRIPT_DESC, "", ""):
        stalker_init()
        try:
            stalker_load_db()
        except:
            w.prnt('', '%s could not load database. Unloading script.' % SCRIPT_NAME)
            # Commit honourable script-icide
            w.hook_signal_send('python_script_remove',
                                     WEECHAT_HOOK_SIGNAL_STRING,
                                     os.path.basename(__FILE__))

        w.hook_command(STALKER_CMD, SCRIPT_DESC,
                      "<user>",
                      '''
                         user: User or hostname to stalk!
                      ''',
                      '%(irc_channel_nicks_hosts)',
                      'stalker_cmd', '')
