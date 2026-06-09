"""GitHub Actions Step Summary 生成脚本。"""
import json


def load_data_from_json(file_path: str) -> list[dict]:
    """从 JSON 文件读取列表数据；读取失败时返回空列表。"""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        # 文件不存在时返回空列表。
        return []
    except json.JSONDecodeError:
        # 文件内容无法解析时返回空列表。
        return []


MD_TEMPLATE = '''
## Balance Record
| **剩余电费** | **照明房间** | **空调房间** |
| --------------- | -------------------- | -------------- |
| {time}  |    {light_Balance}      |    {ac_Balance} |
'''

if __name__ == "__main__":
    # 获取最新记录
    latest_record = load_data_from_json("./page/data/last_30_records.json")[-1]

    # 从最新记录提取数据
    time = latest_record["time"]
    light_balance = latest_record["light_Balance"]
    ac_balance = latest_record["ac_Balance"]

    # 格式化 Markdown 模板并打印
    print(MD_TEMPLATE.format(time=time, light_Balance=light_balance, ac_Balance=ac_balance))
