# -*- coding: utf-8 -*-
import argparse
import json
import requests
import  base64
import os
import  logging
import webrtcvad
from multiprocessing import Pool
from vad import *

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
    level=logging.INFO)

appid = '7450383'


# http://developer.baidu.com/wiki/index.php?title=docs/oauth/client
# 一个 token 一个月有效期
def auth_token(api_key='FupPD0gzcCGfPznizPZW83jy', secret_key='obqE6QiBKqGelvevkdfV5AY6u5noH3jA'):
    auth_url = "https://openapi.baidu.com/oauth/2.0/token?grant_type=client_credentials&client_id=" + api_key + \
               "&client_secret=" + secret_key
    r = requests.get(auth_url)

    result = json.loads(r.text)
    return result['access_token']

# 音频文件长度不超过60s
def speech_recog(audio_file_path, audio_format='wav', rate=16000, channel=1):
    token = auth_token()

    with open(audio_file_path, 'rb') as f:
        audio_file = f.read()

    base_data = base64.b64encode(audio_file).decode('utf-8')
    post_data = {'format': audio_format, 'rate': rate, 'channel': channel, 'token': token,
                 'len': os.path.getsize(audio_file_path), 'speech': base_data, 'cuid': appid}
    url = "http://vop.baidu.com/server_api"
    headers = {'Content-Type': 'application/json; charset=UTF-8', 'Content-Length': len(post_data)}
    r = requests.post(url, data=json.dumps(post_data), headers=headers, timeout=500)  # 不能直接传字典进去, 要转成json 字符串
    result = json.loads(r.text)
    if result['err_no'] != 0:
        return False
    else:
        return result['result']

# 长音频, 先做 vad 切分
def speech_big(audio_file_path, audio_format='wav', rate=16000, channel=1, aggressiveness=2, direc='./'):
    audio, sample_rate = read_wave(audio_file_path)
    vad = webrtcvad.Vad(int(aggressiveness))
    frames = frame_generator(30, audio, sample_rate)
    frames = list(frames)
    segments = vad_collector(sample_rate, 30, 300, vad, frames)
    if not os.path.exists(direc):
        os.makedirs(direc)
    for i, segment in enumerate(segments):
        # todo support multiple format
        path = direc + 'chunk-%002d.wav' % (i,)
        logging.info("now writing:" + path)
        # print(' Writing %s' % (path,))
        write_wave(path, segment, sample_rate)

    file_list = []
    for file_one in os.listdir(direc):
        if file_one.endswith("." + audio_format):
            file_list.append(direc + file_one)

    # request in multiprocess
    i = 0
    res = []
    final_result = []
    pool_audios = Pool(processes=10)
    while i < len(file_list):
        res.append(pool_audios.apply_async(speech_recog, (file_list[i],)))
        i += 1
    pool_audios.close()
    pool_audios.join()
    for one in res:
        try:
            audio = one.get()
            if audio:
                final_result.append(audio)
        except Exception, e:
            logging.info('multi process get audio text exception: ' + str(e))
            continue

    print final_result



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--aggressiveness")
    parser.add_argument("-f", "--file")
    parser.add_argument("-d", "--direc")
    args, _ = parser.parse_known_args()
    aggressiveness = args.aggressiveness
    file = args.file
    direc = args.direc
    speech_big(audio_file_path=file, aggressiveness=aggressiveness, direc=direc)

