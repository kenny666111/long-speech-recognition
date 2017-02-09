# -*- coding: utf-8 -*-
import sys
reload(sys)
sys.setdefaultencoding('utf-8')
import argparse
import json
import requests
import  base64
import os
import webrtcvad
import types
from multiprocessing import Pool
import copy_reg
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
def write_file(filename,num, time_str, content):
    f = open(filename, 'a')
    f.write(str(num) + "\n")
    f.write(time_str + "\n")
    f.write(content + "\n\n")
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

    #格式化每一行字幕
    def make_srt_line(self, num, time_start, time_end, text):
        time = time_start+' '+'-->'+' '+time_end
        return (num, time, text)

    def count_letters(self,word):
        return len(word) - word.count('，')




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
    def speech_big(self, audio_file_path, aggressiveness=2,direc='./'):
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

            write_wave(path, segment[0], sample_rate)
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
                part_duration = seconds-each_duration
                newname = 'merge_'+str(merge_time)+'_'+str(part_duration)+'.wav'
                logging.info("merge writing:" + newname)
                logging.info("merge content:" + str(merge_files))
                self.merge_audio(merge_files, newname)
                merge_files = []
                merge_time = merge_time+1
                seconds = 0
                final_merged_list.append(newname)

            merge_files.append(file_one)


        # last files to merge
        newname = 'merge_' + str(merge_time)+'_'+str(seconds) + '.wav'
        logging.info("last merge writing:" + newname)
        logging.info("last merge content:" + str(merge_files))
        self.merge_audio(merge_files, newname)
        final_merged_list.append(newname)



        # request in multiprocess
        i = 0
        res = []
        final_result = []
        pool_audios = Pool(processes=25)
        while i < len(final_merged_list):
            res.append(pool_audios.apply_async(self.speech_recog, (final_merged_list[i],)))
            i += 1
        pool_audios.close()
        pool_audios.join()
        for one in res:
            try:
                audio_text, audio_file_name = one.get()
                if audio:
                    final_result.append((audio_file_name,audio_text[0]))
            except Exception, e:
                logging.info('multi process get audio text exception: ' + str(e))
                continue


        return final_result

        # for x in final_result:
        #     logging.info(x)

    # 不做合并直接上传
    def speech_big_no_split(self, audio_file_path, aggressiveness=2, direc='./'):
        audio, sample_rate = read_wave(audio_file_path)
        vad = webrtcvad.Vad(int(aggressiveness))
        frames = frame_generator(30, audio, sample_rate)
        frames = list(frames)
        segments = vad_collector(sample_rate, 30, 300, vad, frames)

        file_list = []
        subtitles = {}
        if not os.path.exists(direc):
            os.makedirs(direc)
        for i, segment in enumerate(segments):
            # todo support multiple format
            path = direc + '%002d.wav' % (i,)
            logging.info("above data for:" + path)
            time_end = segment[1]
            time_start = segment[2]
            subtitles[path] = (time_start, time_end)

            #logging.info(each_timestamp)
            # print(' Writing %s' % (path,))
            write_wave(path, segment[0], sample_rate)
            file_list.append(path)


        #exit()

        # request in multiprocess
        i = 0
        res = []
        final_result = []
        pool_audios = Pool(processes=25)
        while i < len(file_list):
            res.append(pool_audios.apply_async(self.speech_recog, (file_list[i],)))
            i += 1
        pool_audios.close()
        pool_audios.join()
        for one in res:
            try:
                audio_text, audio_file_name = one.get()
                if audio:
                    final_result.append((audio_file_name, audio_text[0]))
            except Exception, e:
                logging.info('multi process get audio text exception: ' + str(e))
                continue

        return final_result, subtitles

        # for x in final_result:
        #     logging.info(x[0]+':'+x[1])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--aggressiveness") # set its aggressiveness mode, which is an integer between 0 and 3. 0 is the least aggressive about filtering out non-speech, 3 is the most aggressive
    parser.add_argument("-f", "--file")
    parser.add_argument("-d", "--direc")
    parser.add_argument("-m", "--mode")
    args, _ = parser.parse_known_args()
    aggressiveness = args.aggressiveness
    file = args.file
    direc = args.direc
    mode = args.mode
    # todo put your baidu credentials here
    new = baidu_yuyin('00','xxxxx','xxxxx')
    if mode == '1': # 字幕模式
        all, time_dic = new.speech_big_no_split(audio_file_path=file, aggressiveness=aggressiveness, direc=direc)
        sub_num = 0
        for each in all:
            file_name = each[0]  # merge_7_30.78.wav
            logging.info('now process:' + file_name)
            sub = each[1]
            sub_num = sub_num + 1
            if file_name in time_dic:
                time_start_str = time_dic[file_name][0]
                time_end_str = time_dic[file_name][1]
                result = new.make_srt_line(sub_num, time_start_str, time_end_str, sub)
                write_file('new.srt', result[0], result[1], result[2])

            else:
                logging.info('no time for:' + file_name)
    else:
        all = new.speech_big(audio_file_path=file, aggressiveness=aggressiveness, direc=direc)
        for each in all:
            logging.info(each[1])

