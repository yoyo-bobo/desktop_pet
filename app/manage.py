# app/manage.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory

def main():
    memory.init_db()
    while True:
        print("\n=== 长期记忆管理 ===")
        profile = memory.get_profile()
        if profile:
            for k, v in profile.items():
                print(f"  {k}: {v}")
        else:
            print("  （空）")
        print(f"当前好感度: {memory.get_affection()}/100")
        print("\n操作:")
        print("  1. 修改/新增一条")
        print("  2. 删除一条")
        print("  3. 清空全部画像")
        print("  4. 重置好感度到 20")
        print("  0. 退出")

        choice = input("选择: ").strip()
        if choice == "1":
            k = input("key: ").strip()
            v = input("value: ").strip()
            memory.save_profile(k, v)
            print("已保存")
        elif choice == "2":
            k = input("要删除的 key: ").strip()
            memory.delete_profile(k)
            print("已删除")
        elif choice == "3":
            for k in list(memory.get_profile().keys()):
                memory.delete_profile(k)
            print("已清空")
        elif choice == "4":
            memory.update_affection(20 - memory.get_affection())
            print("已重置")
        elif choice == "0":
            break

if __name__ == "__main__":
    main()