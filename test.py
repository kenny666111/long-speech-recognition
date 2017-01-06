# -*- coding: utf-8 -*-
# write srt file
def write_file(filename,num, time_str, content):
    f = open(filename, 'a')
    f.write(str(num) + "\n")
    f.write(time_str + "\n")
    f.write(content + "\n\n")
    f.close()


write_file('newtt.srt', 1,'xxxxx','xxxxx')


write_file('newtt.srt', 1,'xxxxx','xxxxx')

write_file('newtt.srt', 1,'xxxxx','xxxxx')
