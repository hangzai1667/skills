#!/usr/bin/env python3
"""
全国气象站点索引构建脚本
从 nmc.cn API 获取全国所有省份和城市站点信息，缓存为 JSON 索引文件
供 fetch_weather.py 使用，实现城市名到 stationid 的快速映射
"""

import json
import os
import sys
import urllib.request
import time

BASE_URL = "https://www.nmc.cn/rest/province"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.nmc.cn/"
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(SCRIPT_DIR, "station_index.json")


def fetch_json(url, retries=2):
    """获取 JSON 数据，支持重试"""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
            else:
                print(f"请求失败 {url}: {e}", file=sys.stderr)
                return None


def build_index():
    """构建全国气象站点索引"""
    print("正在获取省份列表...")
    provinces = fetch_json(BASE_URL)
    if not provinces:
        print("获取省份列表失败", file=sys.stderr)
        sys.exit(1)

    # 索引结构
    index = {
        "build_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_provinces": 0,
        "total_stations": 0,
        "provinces": {},      # {省份code: {name, cities: [...]}}
        "city_lookup": {},    # {城市名(小写): {code, province, city}}
        "province_lookup": {} # {省份名(小写): 省份code}
    }

    for prov in provinces:
        prov_code = prov["code"]
        prov_name = prov["name"]
        index["total_provinces"] += 1
        index["province_lookup"][prov_name.lower()] = prov_code

        print(f"  获取 {prov_name} ({prov_code})...", end=" ", flush=True)
        cities = fetch_json(f"{BASE_URL}/{prov_code}")

        if not cities or not isinstance(cities, list):
            print("失败")
            index["provinces"][prov_code] = {"name": prov_name, "cities": []}
            continue

        city_list = []
        for city in cities:
            city_name = city.get("city", "")
            city_code = city.get("code", "")

            city_list.append({"code": city_code, "city": city_name})

            # 城市名到站点映射（支持多种查找方式）
            # 完整城市名
            index["city_lookup"][city_name.lower()] = {
                "code": city_code,
                "province": prov_name,
                "city": city_name
            }

            # 去掉常见后缀的简写查找
            for suffix in ["市", "县", "区", "旗", "州", "盟", "地区"]:
                if city_name.endswith(suffix) and len(city_name) > len(suffix):
                    short_name = city_name[:-len(suffix)]
                    if short_name.lower() not in index["city_lookup"]:
                        index["city_lookup"][short_name.lower()] = {
                            "code": city_code,
                            "province": prov_name,
                            "city": city_name
                        }

            # 省份名+城市名组合
            combo_key = f"{prov_name}{city_name}".lower()
            if combo_key not in index["city_lookup"]:
                index["city_lookup"][combo_key] = {
                    "code": city_code,
                    "province": prov_name,
                    "city": city_name
                }

        index["provinces"][prov_code] = {"name": prov_name, "cities": city_list}
        index["total_stations"] += len(cities)
        print(f"{len(cities)} 个站点")

        # 礼貌间隔，避免过快请求
        time.sleep(0.3)

    # 保存索引
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"\n索引构建完成！")
    print(f"  省份: {index['total_provinces']} 个")
    print(f"  站点: {index['total_stations']} 个")
    print(f"  城市查找条目: {len(index['city_lookup'])} 条")
    print(f"  保存至: {INDEX_FILE}")

    return index


def load_index():
    """加载已有索引，如果不存在则构建"""
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def is_index_stale(max_age_hours=24):
    """检查索引是否过期"""
    if not os.path.exists(INDEX_FILE):
        return True
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            index = json.load(f)
        build_time = time.strptime(index.get("build_time", ""), "%Y-%m-%d %H:%M:%S")
        age_seconds = time.time() - time.mktime(build_time)
        return age_seconds > max_age_hours * 3600
    except Exception:
        return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="全国气象站点索引构建工具")
    parser.add_argument("--force", "-f", action="store_true", help="强制重建索引（即使未过期）")
    parser.add_argument("--search", "-s", type=str, help="搜索城市名，测试索引查找")
    args = parser.parse_args()

    if args.search:
        # 搜索模式
        index = load_index()
        if not index:
            print("索引不存在，请先运行构建（不加参数）")
            sys.exit(1)
        keyword = args.search.lower()
        matches = {k: v for k, v in index["city_lookup"].items() if keyword in k}
        if matches:
            print(f"找到 {len(matches)} 条匹配：")
            for k, v in matches.items():
                print(f"  {v['province']} {v['city']} → stationid={v['code']}")
        else:
            print(f"未找到匹配 '{args.search}' 的城市")
    elif args.force or is_index_stale():
        build_index()
    else:
        index = load_index()
        print(f"索引未过期（构建于 {index.get('build_time')}），使用 --force 强制重建")
        print(f"当前索引: {index['total_provinces']} 省份, {index['total_stations']} 站点, {len(index['city_lookup'])} 查找条目")
