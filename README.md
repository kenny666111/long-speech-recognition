# long-speech-recognition

利用百度语音接口将语音转换为文字, 目前只支持 wav, 请使用 sox 等工具转换为如下参数的 wav 音频



```
Channels       : 1
Sample Rate    : 16000
Precision      : 16-bit
```

---
### Sample usage:

```python
python baidu_speech.py -f zanmei.wav -d ./gkc-cut/ -a 0 -m 2
```
