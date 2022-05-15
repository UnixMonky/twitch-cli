#!/usr/bin/python3
import os
import sys
import requests
import subprocess
import json
import click
from termcolor import colored, COLORS
from urllib.parse import urlencode
import webbrowser
import numpy as np
from config import *
os.system('color')

TWITCH_CLIENT_ID = 'e0fm2z7ufk73k2jnkm21y0gp1h9q2o'
COLORS.update({
    'light_grey': 90,
    'light_red': 91,
    'light_green': 92,
    'light_yellow': 93,
    'light_blue': 94,
    'light_magenta': 95,
    'light_cyan': 96,
    'light_white': 97
})

@click.group(invoke_without_command=True)
@click.pass_context
@click.option('--config', help='Configuration file location')
def main(ctx, config):
    """List or play Twitch streams"""
    if config is not None:
        set_config_path(config)

    load_config()

    if ctx.invoked_subcommand is None:
        cmd_live()

# The cmd_* functions get called when their respective subcommand is executed
# Example: "python3 twitch-cli live" calls "cmd_live"

@main.command('live')
@click.option('--flat', is_flag=True, help='Don\'t show detailed information or prompt')
@click.option('--game', help='Show live streams for a specific game')
@click.option('-q', '--quality', help='Comma-separated stream qualities')
def cmd_live(flat, game, quality):
    """List live channels"""
    list_streams(game=game, flat=flat, playback_quality=quality)

@main.command('vods')
@click.option('--flat', is_flag=True, help='Don\'t show detailed information or prompt')
@click.argument('channel')
@click.option('-q', '--quality', help='Comma-separated stream qualities')
def cmd_vods(channel, flat, quality):
    """List past streams of a channel"""
    list_vods(channel, flat, playback_quality=quality)

@main.command('play')
@click.option('-q', '--quality', help='Comma-separated stream qualities')
@click.argument('channel')
def cmd_play(channel, quality):
    """Play a livestream"""
    play_stream(channel, quality=quality)

# @main.command('follow')
# @click.argument('channel')
# def cmd_follow(channel):
#     """Follow a channel"""
#     follow_channel(channel)

# @main.command('unfollow')
# @click.argument('channel')
# def cmd_unfollow(channel):
#     """Unfollow a channel"""
#     unfollow_channel(channel)

@main.command('auth')
@click.option('--force', '-f', is_flag=True, help='Overwrite existing OAuth token')
def cmd_auth(force):
    """Authenticate with Twitch"""
    config = get_config()
    if (config['oauth'] != '') and (not force):
        print('You are already authenticated.')
        return

    token = authenticate()

    if token != '':
        config['oauth'] = token
        save_config()
        print('Authentication complete.')
    else:
        print('Authentication cancelled.')

def get_available_streams(url):
    command = 'streamlink -j {}'.format(url)
    process = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()
    j_out = json.loads(output.decode())
    streams = []
    for stream in j_out['streams']:
        streams.append(stream)

    return streams

def play_url(url, quality=None):
    if quality is None:
        quality = ''

    command = 'streamlink {} {}'.format(url, quality)
    process = subprocess.Popen(command.split(), stdout=None, stderr=None)
    output, error = process.communicate()

def play_stream(channel, quality=None):
    """Load a stream and open the player"""

    channel_id = get_channel_id(channel)

    if channel_id is None:
        print('The channel "{}" does not exist'.format(channel))
        return

    play_url('twitch.tv/{}'.format(channel), quality=quality)

def list_streams(game=None, flat=False, playback_quality=None):
    """Load the list of streams and prompt the user to chose one."""
    config = get_config()

    if config['oauth'] == '':
        print('You have to provide a Twitch OAuth token to list followed '
              'streams.')
        print('Run "{} auth" to authenticate.'.format(sys.argv[0]))
        sys.exit(1)

    if game is not None:
        streams = helix_get_streams(game)
    else:
        streams = helix_get_streams()

    if streams is None:
        print('Something went wrong while trying to fetch data from the '
              'Twitch API')
        sys.exit(1)
    elif len(streams) == 0:
        print('No streams online now')
        return

    print_stream_list(streams, title='Streams online now', flat=flat)

    if not flat:
        selection = input('Stream ID: ')
        try:
            selection = int(selection)
        except:
            return
    else:
        return

    if not (0 < selection <= len(streams)):
        return

    play_stream(streams[selection - 1]['user_name'], quality=playback_quality)

def list_vods(channel, flat, playback_quality=None):
    vods = get_channel_vods(channel)

    if vods is None:
        return
    elif len(vods) == 0:
        print('No recent VODs for {}'.format(channel))
        return

    print_vod_list(vods, title='{}\'s recent VODs'.format(channel))
    if not flat:
        selection = input('VOD ID: ')
        try:
            selection = int(selection)
        except:
            return

        if (0 < selection <= len(vods)):
            play_url(vods[selection-1]['url'], quality=playback_quality)

def get_channel_vods(channel):
    config = get_config()
    user_id = get_channel_id(channel)

    if user_id is None:
        print('The channel "{}" does not exist'.format(channel))
        return

    query = { 'user_id' : user_id }
    url = 'https://api.twitch.tv/helix/videos?{}'.format(urlencode(query))
    headers = {
        'client-id': TWITCH_CLIENT_ID,
        'Authorization': 'Bearer {}'.format(config['oauth'])
    }
    request = requests.get(url, headers=headers)
    response = request.json()

    if 'data' not in response:
        return None

    return response['data']

def print_stream_list(streams, title=None, flat=False):
    if title and not flat:
        print(title)
        print('')

    if flat:
        format = '{1[user_name]}'
    else:
        ind_len = len(str(len(streams)))
        bullet          = '{0: >' + str(ind_len + 2) + 's}'
        display_name    = '{1[user_name]}'
        status          = '{1[title]}'
        game            = '{1[game_name]}'
        viewers         = '[{1[viewer_count]} viewers]'
        format = (colored(bullet + ' ',         'light_red')
                + colored(display_name + ': ',  'light_blue', attrs=['bold'])
                + colored(game + ' ',           'light_yellow')
                + colored(viewers + '\n',       'light_green')
                + (' ' * (ind_len + 3))
                + colored(status + '\n',        'light_grey'))

    i = 1
    for stream in streams:
        print(format.format('[' + str(i) + ']', stream))
        i += 1

def print_vod_list(vods, title=None, flat=False):
    if title and not flat:
        print(title)
        print('')

    if flat:
        format = '{1[url]}'
    else:
        ind_len = len(str(len(vods)))
        bullet  = '{0: >' + str(ind_len + 2) + 's}'
        title   = '{1[title]}'
        duration= 'Duration: {1[duration]}'
        date    = 'Recorded: {1[created_at]}'
        format = (colored(bullet + ' ',      'light_red')
                + colored(title + '\n',      'light_blue', attrs=['bold'])
                + (' ' * (ind_len + 3))
                + colored(date + '\n',       'light_grey',)
                + (' ' * (ind_len + 3))
                + colored(duration + '\n',   'light_grey'))

        i = 1
        for vod in vods:
            print(format.format('[' + str(i) + ']', vod))
            i += 1

# def follow_channel(channel):
#     own_id = get_own_channel_id()
#     channel_id = get_channel_id(channel)

#     if channel_id is None:
#         print('The channel "{}" does not exist'.format(channel))
#         return

#     data = '{{"from_id": "{}","to_id": "{}"}}' .format(own_id, channel_id)

#     url = 'users/follows'
#     response = helixapi_request(url, method='post', data=data)
#     print('You now follow {}'.format(channel))

# def unfollow_channel(channel):
#     own_id = get_own_channel_id()
#     channel_id = get_channel_id(channel)

#     if channel_id is None:
#         print('The channel "{}" does not exist'.format(channel))
#         return

#     query = {
#         'from_id' : own_id,
#         'to_id' : channel_id
#     }
#     url = 'users/follows?{}'.format(urlencode(query))
#     response = helixapi_request(url, method='delete')

#     print('You don\'t follow {} anymore'.format(channel))

def get_own_channel_id():
    url = 'users'
    response = helixapi_request(url)

    return response['data'][0]['id']

def get_channel_id(name):
    query = { 'login': name }
    url = 'users?{}'.format(urlencode(query))
    response = helixapi_request(url)

    if response['data'][0]['created_at'] is None:
        return None

    return response['data'][0]['id']

def helix_user_follows():
    config = get_config()
    own = get_own_channel_id()

    url = 'https://api.twitch.tv/helix/users/follows?from_id={}&first=100' .format(int(own))
    headers = {
        'client-id': TWITCH_CLIENT_ID,
        'Authorization': 'Bearer {}'.format(config['oauth'])
    }
    request = requests.get(url, headers=headers)
    response = request.json()

    if response['total'] == 0:
        return None

    ids=''
    for id_ in response['data']:
        ids = ids + 'user_id=' + id_['to_id'] + '&'

    return ids[:-1]

def helix_get_streams(game=''):
    config = get_config()
    games = helix_get_games(game)
    user_follows = helix_user_follows()

    url = 'https://api.twitch.tv/helix/streams?{}' .format(user_follows + games)
    headers = {
        'client-id': TWITCH_CLIENT_ID,
        'Authorization': 'Bearer {}'.format(config['oauth'])
    }
    request = requests.get(url, headers=headers)
    response = request.json()

    flag = not np.any(response['data'])
    if flag:
         print("No followed streamers are live.")
         sys.exit(1)
         
    if 'user_name' not in response['data'][0]:
        return None

    return response['data']

def helix_get_games(game=''):
    if game == '':
        return ''

    config = get_config()

    query = { 'query': game }
    url = 'https://api.twitch.tv/helix/search/categories?{}' .format(urlencode(query))
    headers = {
        'client-id': TWITCH_CLIENT_ID,
        'Authorization': 'Bearer {}'.format(config['oauth'])
    }
    request = requests.get(url, headers=headers)
    response = request.json()

    flag = not np.any(response['data'])
    if flag:
        return None

    if 'name' not in response['data'][0]:
        return None

    ids=''
    for id_ in response['data']:
        ids = ids + 'game_id=' + id_['id'] + '&'

    return ids[:-1]

def authenticate():
    query = {
        'response_type': 'token',
        'client_id': TWITCH_CLIENT_ID,
        'redirect_uri': 'https://butt4cak3.github.io/twitch-cli/oauth.html',
        'scope': 'user:edit:follows'
    }
    url = ('https://id.twitch.tv/oauth2/authorize?{}'
           .format(urlencode(query, safe=':/-')))

    try:
        if not webbrowser.open_new_tab(url):
            raise webbrowser.Error
    except webbrowser.Error:
        print('Couldn\'t open a browser. Open this URL in your browser to '
              'continue: ')
        print(url)
        return

    token = input('OAuth token: ')
    return token.strip()

def helixapi_request(url, method='get', data=None):
    config = get_config()

    url = 'https://api.twitch.tv/helix/' + url
    headers = {
        'Authorization': 'Bearer {}'.format(config['oauth']),
        'Client-ID': TWITCH_CLIENT_ID
    }
    if method == 'get':
        request = requests.get(url, headers=headers)
    elif method == 'post':
        headers['Content-Type'] = 'application/json'
        request = requests.post(url, headers=headers, data=data)
    elif method == 'delete':
        request = requests.delete(url, headers=headers)

    try:
        data = request.json()
    except:
        print(request.text)
        return None

    try:
        data['status'] == 401
    except KeyError:
        return data

    print("OAuth Token has expired.  Please run 'auth --force' to generate a new one.")
    sys.exit(1)

if __name__ == '__main__':
    main()
