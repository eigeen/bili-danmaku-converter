#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Version: 0.0.1
Author: Eigeen
Homepage: https://github.com/eigeen/bili-danmaku-converter
"""

from lxml import etree

# 基础模板由Aegisub导出的文件提取而来
basic_template = '''[Script Info]
; Converted by bili-danmaku-converter
; https://github.com/eigeen/bili-danmaku-converter
Title: {title}
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None
RoomID: {roomid}
Host: {name}
StartLiveTime: {livetime}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TypeA,黑体,40,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,1,1,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'''

dialogue_raw = "Dialogue: 0,{start_moment},{end_moment},TypeA,,0,0,0,,{effect}{username}: {text}\n"


class Parser(object):
    def __init__(self, filepath):
        self.filepath = filepath
        self.tree = etree.parse(filepath)
        self.basicinfo = None
        self.normal_dm = None
        self.gift_dm = None
        self.active_queue = None
        self.standby_queue = None

    @staticmethod
    def starttime(time):
        """
        直播开始时间
        :param time: 2021-01-26T21:01:31.9801837+08:00
        :return: 2021-01-26T21:01:31
        """
        return time[:19]

    @staticmethod
    def parse_realtime(seconds):
        """
        解析时间
        :param seconds: 14.8218419
        :return: hh:mm:ss
        """
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        m = "{:0>2d}".format(int(m))
        s = "{:0>5.2f}".format(s)
        return "{}:{}:{}".format(str(int(h)), m, s)

    @staticmethod
    def parse_starttime(seconds):
        """
        解析弹幕开始时间
        :param seconds: 14.8218419
        :return: hh:mm:ss
        """
        return Parser.parse_realtime(seconds)

    @staticmethod
    def parse_color(color10):
        color16 = hex(color10)
        return str(color16)[2:]

    @staticmethod
    def parse_livetime(time):
        """

        :param time: 2021-01-26T21:01:31.9801837+08:00
        :return: 2021-01-26T21:01:31
        """
        return time[:19]

    @staticmethod
    def parse_normal_info(infostr):
        """

        :param infostr: "30.7448226,1,25,4546550,1611666122726,0,9670369,0"
        :return:
        """
        sinfo = infostr.split(",")
        infodict = {
            'time': sinfo[0],
            'mode': sinfo[1],
            'fontsize': sinfo[2],
            'color': sinfo[3],
            'timestamp': sinfo[4],
            'uid': sinfo[6]
        }
        return infodict

    def parse_basicinfo(self):
        """
        解析直播间基础信息
        :return:
        """
        basicinfo = {}
        bps = self.tree.xpath("//BililiveRecorderRecordInfo")
        for bp in bps:
            basicinfo = bp.attrib
            # basicinfo = {
            #     'roomid': '378461',
            #     'name': '肉松owo',
            #     'start_time': '2021-01-26T21:01:31.9801837+08:00'
            # }
            basicinfo['livetime'] = Parser.parse_livetime(basicinfo['start_time'])
        self.basicinfo = basicinfo

    def parse_normal_danmu(self):
        """
        解析普通弹幕
        :return:
        """
        dm_data = []
        dm_info = self.tree.xpath("//d/@p")
        dm_usernames = self.tree.xpath("//d/@user")
        dm_contents = self.tree.xpath("//d/text()")
        for dm_info_tmp, dm_username_tmp, dm_content_tmp in zip(dm_info, dm_usernames, dm_contents):
            dm_info_dict = Parser.parse_info(dm_info_tmp)
            dm_info_dict['username'] = dm_username_tmp
            dm_info_dict['content'] = dm_content_tmp
            dm_data.append(dm_info_dict.copy())
        self.normal_dm = dm_data

    def parse_gift_danmu(self):
        """
        解析礼物
        :return:
        """
        gf_data = []
        gf_info = self.tree.xpath("//gift")
        for gf_info_tmp in gf_info:
            gf_dict_tmp = gf_info_tmp.attrib
            gf_info_dict = {'time': gf_dict_tmp['ts'],
                            'username': gf_dict_tmp['user'],
                            'giftname': gf_dict_tmp['giftname'],
                            'giftcount': gf_dict_tmp['giftcount']
                            }
            gf_data.append(gf_info_dict)
        self.gift_dm = gf_data

    def calc_moment(self):
        self.active_queue = []
        self.standby_queue = self.normal_dm.copy()

        for i in range(len(self.normal_dm)):
            while True:
                if len(self.active_queue) < 7:
                    self.active_queue.append(self.standby_queue[0])
                    del self.standby_queue[0]
                elif i >= len(self.normal_dm) - 7:
                    self.standby_queue.append(self.active_queue[-1])
                    break
                else:
                    break

            last_time = "{:.2f}".format(float(self.standby_queue[0]['time']) - float(self.active_queue[0]['time']))
            self.active_queue[0]['end_time'] = float(last_time) + float(self.active_queue[0]['time'])
            self.active_queue[0]['start_moment'] = self.parse_starttime(float(self.active_queue[0]['time']))
            self.active_queue[0]['end_moment'] = self.parse_starttime(float(self.active_queue[0]['end_time']))
            self.normal_dm[i] = self.active_queue[0]
            del self.active_queue[0]

    def export(self):
        """
        导出ASS
        :return:
        """
        self.write_basicinfo()
        self.write_normal_dm()

    def write_basicinfo(self):
        filename = self.filepath.split("\\")[-1]
        with open(r".\export\danmaku.ass", "w", encoding="utf8") as fp:
            fp.write(basic_template.format(title=filename, **self.basicinfo))

    def write_normal_dm(self):
        with open(r".\export\danmaku.ass", "a", encoding="utf8") as fp:
            for n in range(len(self.normal_dm)):
                start_moment = self.normal_dm[n]['start_moment']
                end_moment = self.normal_dm[n]['end_moment']
                color = self.parse_color(eval(self.normal_dm[n]['color']))
                # effect = r"{\c&H" + color + "&}"   + move
                effect = ""
                text = self.normal_dm[n]['content']
                fp.write(
                    dialogue_raw.format(start_moment=start_moment, end_moment=end_moment, text=text, effect=effect))


def main(filepath):
    p = Parser(filepath)
    p.parse_basicinfo()
    p.parse_normal_danmu()
    # p.parse_gift_danmu()
    p.calc_moment()
    p.export()


if __name__ == "__main__":
    path = r"录制-21727410-20210514-205537-直播测试，新买了设备.xml"
    main(path)
