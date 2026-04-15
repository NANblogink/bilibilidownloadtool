##出现乱码文件的时候的删除工具，虽然没啥用
import os
import shutil

# 删除有问题的temp目录
temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")

if os.path.exists(temp_dir):
    try:
        # 尝试使用shutil.rmtree删除
        shutil.rmtree(temp_dir)
        print(f"成功删除temp目录: {temp_dir}")
    except Exception as e:
        print(f"使用shutil.rmtree删除失败: {e}")
        print("尝试使用其他方法...")
        
        # 尝试使用Windows的cmd命令删除
        import subprocess
        try:
            subprocess.run(['cmd', '/c', f'rd /s /q "{temp_dir}"'], check=True)
            print(f"成功使用cmd删除temp目录: {temp_dir}")
        except Exception as e2:
            print(f"使用cmd删除也失败: {e2}")
else:
    print(f"temp目录不存在: {temp_dir}")

