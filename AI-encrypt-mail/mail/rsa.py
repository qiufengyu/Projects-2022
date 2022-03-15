#-*- coding: utf-8 -*-

import base64
from Cryptodome import Random
from Cryptodome.PublicKey import RSA
from Cryptodome.Cipher import PKCS1_v1_5 as Cipher_pkcs1_v1_5
from Cryptodome.Signature import PKCS1_v1_5 as Signature_pkcs1_v1_5


class MailRSA():
    def __init__(self):
        self.random_generator = Random.new().read
        self.rsa = RSA.generate(1024, self.random_generator)
        self.cut_separator = '##'

    def generate_pub_priv(self):
        priv = str(self.rsa.exportKey(), encoding='utf-8')
        pub = str(self.rsa.publickey().exportKey(), encoding='utf-8')
        return priv, pub

    def cut_string(self, message: str, length=117):
        result = []
        temp_char = []
        for word in message:
            word_en = word.encode('utf-8')
            temp_en = "".join(temp_char).encode('utf-8')
            if len(temp_en) + len(word_en) <= length:
                temp_char.append(word)
            else:
                result.append("".join(temp_char))
                temp_char.clear()
                temp_char.append(word)
        result.append("".join(temp_char))
        return result

    def __rsa_encrypt(self, plain_text, pub_key):
        text = plain_text.encode('utf-8')
        rsakey = RSA.importKey(pub_key)
        cipher = Cipher_pkcs1_v1_5.new(rsakey)
        secret_text = base64.b64encode(cipher.encrypt(text))
        secret_text_decode = secret_text.decode('utf-8')
        return secret_text_decode


    def encrypt(self, plain_text: str, pub_key):
        result = []
        cut_lines = self.cut_string(plain_text)
        for cut_line in cut_lines:
            context = self.__rsa_encrypt(cut_line, pub_key)
            result.append(context)
        return self.cut_separator.join(result)


    def __rsa_decrypt(self, secret_text, priv_key):

        text = base64.b64decode(secret_text)
        rsakey = RSA.importKey(priv_key)
        cipher = Cipher_pkcs1_v1_5.new(rsakey)
        plain_text = cipher.decrypt(text, sentinel = Random.get_random_bytes(16))
        plain_text_decode = plain_text.decode('utf-8')
        return plain_text_decode

    def decrypt(self, content, priv_key):
        result = []
        lines = content.split(self.cut_separator)
        for line in lines:
            context = self.__rsa_decrypt(line.strip(), priv_key)
            result.append(context)
        return "".join(result)

if __name__ == '__main__':
    mail_rsa = MailRSA()
    priv, pub = mail_rsa.generate_pub_priv()
    print(pub)
    print(priv)
    s = '广告：IP网络电话包年卡1000元(长途市话全包:QQ39494297)最快的论坛邮址搜索专家、最好的邮件群发专家论坛短信群发专家\n www.1234m.com朋友，您好！如何赚钱一、简介一边下载一边看看下面的文字吧，绝不会让你会悔的！如果实在是没兴趣，不看也罢。一边一网，一边赚钱！每小时高达 8.4 元，多么惬意！每月再赚 150美金不是梦！1小时赚1.66美元，装了宽带别浪费。'
    en_s = mail_rsa.encrypt(s, pub)
    print(en_s)
    de_s = mail_rsa.decrypt(en_s, priv)
    print(de_s)


