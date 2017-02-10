# long-speech-recognition

利用百度语音接口将语音转换为文字, 目前只支持 wav, 请使用 sox 等工具转换为如下参数的 wav 音频

多数语音 API 都只支持60s 以下短音频, 这个脚本会自动把长音频切成短音频后转换成中文.


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
