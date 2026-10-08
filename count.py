# def decimal_to_hexadecimal(decimal_number):
#     # 将十进制数字转换为十六进制字符串，并去掉 '0x' 前缀
#     return hex(decimal_number)[2:]
#
# if __name__ == "__main__":
#     try:
#         # 从用户处获取输入的十进制数字
#         user_input = int(input("请输入一个十进制数字: "))
#         # 进行转换
#         hex_result = decimal_to_hexadecimal(user_input)
#         # 打印结果
#         print(f"十进制数字 {user_input} 的十六进制表示是: {hex_result}")
#     except ValueError:
#         print("请输入一个有效的十进制数字。")


# def hexadecimal_to_decimal(hexadecimal_string):
#     # 将十六进制字符串转换为十进制数字
#     return int(hexadecimal_string, 16)
#
# if __name__ == "__main__":
#     try:
#         # 从用户处获取输入的十六进制字符串
#         user_input = input("请输入一个十六进制数字（例如 1A3F）: ")
#         # 进行转换
#         decimal_result = hexadecimal_to_decimal(user_input)
#         # 打印结果
#         print(f"十六进制数字 {user_input} 的十进制表示是: {decimal_result}")
#     except ValueError:
#         print("请输入一个有效的十六进制数字。")

def count_characters(input_string):
    # 统计字符串中的字符个数
    return len(input_string)

if __name__ == "__main__":
    # 从用户处获取输入字符串
    user_input = input("请输入一串字符串: ")
    # 计算并打印字符的个数
    num_characters = count_characters(user_input)
    print(f"输入的字符串中有 {num_characters} 个字符。")

# hash_bytes = b'&)G\x9a\xaai\xd2d\xbc&v\x16}3<u7\x98\xc9r\xe1\xb1\x81w\nxY\x1b\x14\x02\x8b\x94'
# hash_hex = hash_bytes.hex()
# print(hash_hex)

