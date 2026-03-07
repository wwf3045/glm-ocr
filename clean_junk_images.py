"""
清理 OCR 产生的垃圾图片（向日葵背景、齿轮图标、侧边栏小图标）
同时清理 Markdown 文件中对已删除图片的引用
"""
import os
import re

OUTPUT_DIR = "output"

# 垃圾图片判定阈值
SUNFLOWER_SIZE = 3.2 * 1024 * 1024   # ~3.2MB 向日葵背景
GEAR_MAX_SIZE = 3 * 1024              # <3KB 齿轮图标
SIDEBAR_MAX_SIZE = 2.5 * 1024         # <2.5KB 侧边栏小图标


def is_junk_image(filepath, filesize):
    """判断是否为垃圾图片"""
    # 约 3.2MB 的向日葵背景图
    if abs(filesize - SUNFLOWER_SIZE) < 100 * 1024:
        return True
    # <3KB 的齿轮图标
    if filesize < GEAR_MAX_SIZE:
        return True
    # <2.5KB 的侧边栏小图标
    if filesize < SIDEBAR_MAX_SIZE:
        return True
    return False


def clean_md_references(md_path, deleted_images):
    """清理 Markdown 中对已删除图片的引用"""
    if not deleted_images:
        return

    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    original = content
    for img_name in deleted_images:
        # 匹配 ![...](images/xxx) 或 ![...](xxx)
        pattern = rf'!\[.*?\]\([^)]*{re.escape(img_name)}[^)]*\)'
        content = re.sub(pattern, "", content)

    if content != original:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(content)


def main():
    total_deleted = 0
    total_freed = 0

    for folder_name in os.listdir(OUTPUT_DIR):
        folder_path = os.path.join(OUTPUT_DIR, folder_name)
        if not os.path.isdir(folder_path):
            continue

        images_dir = os.path.join(folder_path, "images")
        if not os.path.exists(images_dir):
            continue

        deleted_images = []
        for img_name in os.listdir(images_dir):
            img_path = os.path.join(images_dir, img_name)
            if not os.path.isfile(img_path):
                continue

            filesize = os.path.getsize(img_path)
            if is_junk_image(img_path, filesize):
                os.remove(img_path)
                deleted_images.append(img_name)
                total_deleted += 1
                total_freed += filesize

        # 清理 Markdown 中的引用
        if deleted_images:
            for md_file in os.listdir(folder_path):
                if md_file.endswith(".md"):
                    clean_md_references(
                        os.path.join(folder_path, md_file), deleted_images
                    )
            print(f"{folder_name}: 删除 {len(deleted_images)} 张垃圾图片")

    print(f"\n总计删除 {total_deleted} 张，释放 {total_freed / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
