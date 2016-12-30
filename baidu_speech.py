# -*- coding: utf-8 -*-
import argparse
import json
import requests
import  base64
import os
import  logging
import webrtcvad
import types
from multiprocessing import Pool
import copy_reg
import wave
import contextlib
from vad import *
from pydub import AudioSegment

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
    level=logging.INFO)

def _pickle_method(m):
    if m.im_self is None:
        return getattr, (m.im_class, m.im_func.func_name)
    else:
        return getattr, (m.im_self, m.im_func.func_name)

copy_reg.pickle(types.MethodType, _pickle_method)


# write srt file
def write_file(filename, x):
    f = open(filename, 'a')
    f.write(x + '\n')
    f.close()

class baidu_yuyin:

    def __init__(self, appid, api_key, secret_key):
        self.appid = appid
        self.secret_key = secret_key
        self.api_key = api_key
        self.token = self.auth_token()

    # http://developer.baidu.com/wiki/index.php?title=docs/oauth/client
    # 一个 token 一个月有效期
    def auth_token(self):
        auth_url = "https://openapi.baidu.com/oauth/2.0/token?grant_type=client_credentials&client_id="+self.api_key+\
                   "&client_secret="+self.secret_key
        r = requests.get(auth_url)

        result = json.loads(r.text)
        return result['access_token']


    # get duration of wav file
    def get_duration(self, audio_path):
        fname = audio_path
        with contextlib.closing(wave.open(fname, 'r')) as f:
            frames = f.getnframes()
            rate = f.getframerate()
            duration = frames / float(rate)
            return duration

    # 合并音频文件
    def merge_audio(self, audio_path_list, name):
        merged = AudioSegment.from_wav(audio_path_list[0])
        for idx, val in enumerate(audio_path_list):
            if idx == 0:
                continue
            each = AudioSegment.from_wav(val)
            merged = merged+each

        merged.export(name, format="wav")

        return merged


    # 音频文件长度不超过60s
    def speech_recog(self, audio_file_path, audio_format='wav', rate=16000, channel=1):
        with open(audio_file_path, 'rb') as f:
            audio_file = f.read()

        base_data = base64.b64encode(audio_file).decode('utf-8')
        post_data = {'format':audio_format, 'rate':rate, 'channel':channel, 'token':self.token,
                     'len':os.path.getsize(audio_file_path), 'speech':base_data,'cuid':self.appid}
        url = "http://vop.baidu.com/server_api"
        headers = {'Content-Type': 'application/json; charset=UTF-8', 'Content-Length':len(post_data)}
        r = requests.post(url, data=json.dumps(post_data),headers=headers, timeout=500) # 不能直接传字典进去, 要转成json 字符串
        result = json.loads(r.text)
        if result['err_no']!=0:
            return False
        else:
            return result['result'], audio_file_path

    # 长音频, 先做 vad 切分
    def speech_big(self, audio_file_path, audio_format='wav', rate=16000, channel=1,aggressiveness=2,direc='./'):
        audio, sample_rate = read_wave(audio_file_path)
        vad = webrtcvad.Vad(int(aggressiveness))
        frames = frame_generator(30, audio, sample_rate)
        frames = list(frames)
        segments = vad_collector(sample_rate, 30, 300, vad, frames)
        file_list = []
        if not os.path.exists(direc):
            os.makedirs(direc)
        for i, segment in enumerate(segments):
            #todo support multiple format
            path = direc+'%002d.wav' % (i,)
            logging.info("now writing:" + path)
            #print(' Writing %s' % (path,))
            write_wave(path, segment, sample_rate)
            file_list.append(path)

        # merge small files to save requests, make sure new file less than 59s
        merge_time = 1
        seconds = 0
        merge_files = []
        final_merged_list = []
        logging.info("merge start")
        for file_one in file_list:
            each_duration = self.get_duration(file_one)
            seconds = seconds+each_duration
            if seconds > 59:
                newname = 'merge_'+str(merge_time)+'.wav'
                logging.info("merge writing:" + newname)
                logging.info("merge content:" + str(merge_files))
                self.merge_audio(merge_files, newname)
                merge_files = []
                merge_time = merge_time+1
                seconds = 0
                final_merged_list.append(newname)

            merge_files.append(file_one)


        # last files to merge
        newname = 'merge_' + str(merge_time) + '.wav'
        logging.info("last merge writing:" + newname)
        logging.info("last merge content:" + str(merge_files))
        self.merge_audio(merge_files, newname)


        # request in multiprocess
        i = 0
        res = []
        final_result = []
        pool_audios = Pool(processes=19)
        while i < len(final_merged_list):
            res.append(pool_audios.apply_async(self.speech_recog, (final_merged_list[i],)))
            i += 1
        pool_audios.close()
        pool_audios.join()
        for one in res:
            try:
                audio_text, audio_file_name = one.get()
                if audio:
                    final_result.append(audio_file_name+':'+audio_text[0])
            except Exception, e:
                logging.info('multi process get audio text exception: ' + str(e))
                continue

        for x in final_result:
            logging.info(x)





if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--aggressiveness")
    parser.add_argument("-f", "--file")
    parser.add_argument("-d", "--direc")
    args, _ = parser.parse_known_args()
    aggressiveness = args.aggressiveness
    file = args.file
    direc = args.direc
    new = baidu_yuyin('7450383','FupPD0gzcCGfPznizPZW83jy','obqE6QiBKqGelvevkdfV5AY6u5noH3jA')
    #print new.auth_token()
    new.speech_big(audio_file_path=file, aggressiveness=aggressiveness, direc=direc)
    #todo 关于时间轴的思路, 可以先用 agg=3拆分音频, 记下断点, 然后合并上传识别

