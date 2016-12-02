import sqlite3
from slackclient import SlackClient
import time
import os
import sys


conn = sqlite3.connect(sys.argv[1])

def format_list(query, header, format):
    c = conn.cursor()
    i = 1
    lines = [header]
    for row in c.execute(query):
        lines.append(format % ((i,) + row))
        i += 1

    return '\n'.join(lines)


def print_score():
    return format_list('select name, (cast(score as float) - 1000) / (rounds_tr + rounds_ct) as spr, score, cast(kills as float)/deaths from rankme order by spr desc',
                       '%23s%8s%6s%6s' % ('Nick', 'Score/r', 'Score', 'KDR'),
                       '%2d.%20s%8.02f%6d%6.02f')


def print_headshots():
    return format_list('select name, cast(headshots as float) / (rounds_tr + rounds_ct) as spr, headshots from rankme order by spr desc',
                       '%23s%8s%6s' % ('Nick', 'HShot/r', 'Total'),
                       '%d. %20s%8.02f%6d')

# constants
BOT_ID = os.environ.get("BOT_ID")
AT_BOT = "<@" + BOT_ID + ">"


def handle_command(command, channel):
    response = "Not sure what you mean. Try *ranking* or *headshots*."
    if command.startswith('ranking'):
        response = '```\n' + print_score() + '```\n:cs: :c4: :cs:'
    elif command.startswith('headshots'):
        response = '```\n' + print_headshots() + '```\n:disappointed_relieved::gun:'
    slack_client.api_call("chat.postMessage", channel=channel,
                          text=response, as_user=True)


def parse_slack_output(slack_rtm_output):
    """
        The Slack Real Time Messaging API is an events firehose.
        this parsing function returns None unless a message is
        directed at the Bot, based on its ID.
    """
    output_list = slack_rtm_output
    if output_list and len(output_list) > 0:
        for output in output_list:
            if output and 'text' in output and AT_BOT in output['text']:
                # return text after the @ mention, whitespace removed
                return output['text'].split(AT_BOT)[1].strip().lower(), \
                    output['channel']
    return None, None


last_score = None
last_active = None
is_active = False


def check_active():
    global last_score, last_active, is_active
    c = conn.cursor()
    score = c.execute('select sum(score) from rankme').fetchone()[0]
    now = time.time()

    print 'Score is %d at % .0f' % (score, now)

    if not last_score is None and score != last_score:
        if not is_active:
            is_active = True
            print 'The game has begun'
            slack_client.api_call("chat.postMessage", channel='#lanparty',
                                  text='The game is on! :c4:', as_user=True)
        last_score = score
        last_active = now
    elif not last_active is None and now - last_active > 60:
        is_active = False
        print 'The game has ended'
        slack_client.api_call("chat.postMessage", channel='#lanparty',
                              text='http://giphy.com/gifs/arnold-schwarzenegger-windows-cs-CFjw7eSxjJL8I\n\n' + print_score(), as_user=True)


if __name__ == "__main__":
    slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))
    READ_WEBSOCKET_DELAY = 1  # 1 second delay between reading from firehose

    if slack_client.rtm_connect():
        print("Bot connected and running.")
        count = 0
        while True:
            if count % 10 == 0:
                check_active()

            count += 1

            command, channel = parse_slack_output(slack_client.rtm_read())
            if command and channel:
                print 'Received "%s" on channel %s' % (command, channel)
                handle_command(command, channel)
            time.sleep(READ_WEBSOCKET_DELAY)
    else:
        print("Connection failed. Invalid Slack token or bot ID?")
