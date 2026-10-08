import os
import shutil

def rename_and_move_pdfs(original_folder, rename_folder):
    # 如果目标文件夹不存在，则创建
    if not os.path.exists(rename_folder):
        os.makedirs(rename_folder)

    for file_name in os.listdir(original_folder):
        # 检查文件是否是PDF文件
        if file_name.endswith(".pdf"):
            # 去掉多余的".pdf"并清理多余的空格
            new_name = file_name.replace(".pdf.pdf", ".pdf").replace(" .pdf", ".pdf")
            old_file = os.path.join(original_folder, file_name)
            new_file = os.path.join(rename_folder, new_name)
            # 如果文件名被修改或者需要移动
            if not os.path.exists(new_file):  # 防止文件名冲突
                shutil.copy2(old_file, new_file)  # 将文件复制到目标文件夹
                print(f"Moved and Renamed: {file_name} -> {new_name}")
            else:
                print(f"Skipped (already exists): {new_name}")

if __name__ == "__main__":
    original_folder = r"C:\Users\luyan\Desktop\论文"
    rename_folder = r"C:\Users\luyan\Desktop\论文\rename"
    rename_and_move_pdfs(original_folder, rename_folder)
