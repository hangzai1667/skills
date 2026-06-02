#!/usr/bin/env python3
"""
全国天气查询脚本
支持通过城市名查询全国 2,500+ 个气象站点的实时天气、7天预报和逐小时数据
数据来源: 中央气象台 (nmc.cn)
"""

import json
import os
import sys
import urllib.request
import argparse
from datetime import datetime

# ============ 路径配置 ============
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(SCRIPT_DIR, "station_index.json")
BUILD_SCRIPT = os.path.join(SCRIPT_DIR, "build_station_index.py")

# ============ API 配置 ============
WEATHER_API = "https://www.nmc.cn/rest/weather"
PROVINCE_API = "https://www.nmc.cn/rest/province"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.nmc.cn/"
}

# 风向角度转中文
WIND_DIRECTIONS = {
    0: "北风", 22.5: "北东北风", 45: "东北风", 67.5: "东东北风",
    90: "东风", 112.5: "东东南风", 135: "东南风", 157.5: "南东南风",
    180: "南风", 202.5: "南西南风", 225: "西南风", 247.5: "西西南风",
    270: "西风", 292.5: "西西北风", 315: "西北风", 337.5: "北西北风",
    360: "北风"
}


# ============ 工具函数 ============

def is_valid(value):
    """检查值是否为有效数据（排除 9999 等占位符）"""
    if value is None:
        return False
    if isinstance(value, (int, float)) and value >= 9999:
        return False
    if isinstance(value, str) and value.strip() in ("9999", "-", ""):
        return False
    return True


def wind_degree_to_direction(degree):
    """将风向角度转为中文方向"""
    if not is_valid(degree):
        return None
    degree = degree % 360
    closest = min(WIND_DIRECTIONS.keys(), key=lambda x: abs(x - degree))
    return WIND_DIRECTIONS[closest]


def format_temperature(temp):
    """格式化温度值"""
    if not is_valid(temp):
        return None
    try:
        return f"{float(temp):.0f}°C"
    except (ValueError, TypeError):
        return None


# ============ 城市查找 ============

def load_index():
    """加载站点索引"""
    if not os.path.exists(INDEX_FILE):
        return None
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def find_station(city_name):
    """
    根据城市名查找气象站点
    返回 (stationid, province, city_display_name) 或 None
    """
    keyword = city_name.strip().lower()

    # 1. 尝试从本地索引查找
    index = load_index()
    if index and "city_lookup" in index:
        # 精确匹配
        if keyword in index["city_lookup"]:
            info = index["city_lookup"][keyword]
            return info["code"], info["province"], info["city"]

        # 模糊匹配：包含关键词
        candidates = []
        for key, val in index["city_lookup"].items():
            if keyword in key or key in keyword:
                candidates.append(val)

        if candidates:
            # 优先匹配省份名+城市名完全包含关键词的
            for c in candidates:
                if keyword == c["city"].lower() or keyword == c["city"].lower().rstrip("市区县旗州盟"):
                    return c["code"], c["province"], c["city"]
            # 否则返回第一个
            best = candidates[0]
            return best["code"], best["province"], best["city"]

    # 2. 索引不存在或未命中，尝试动态查找
    # 先尝试从省份列表匹配
    try:
        req = urllib.request.Request(PROVINCE_API, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            provinces = json.loads(resp.read().decode("utf-8"))

        for prov in provinces:
            # 如果城市名包含省份关键词，先查该省
            prov_name = prov["name"].lower()
            if keyword.startswith(prov_name[:2]):
                return _search_in_province(prov["code"], keyword)

        # 没有省份线索，逐省搜索（只搜索主要城市）
        for prov in provinces:
            result = _search_in_province(prov["code"], keyword)
            if result:
                return result
    except Exception:
        pass

    return None


def _search_in_province(prov_code, keyword):
    """在某省城市列表中搜索"""
    try:
        req = urllib.request.Request(f"{PROVINCE_API}/{prov_code}", headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            cities = json.loads(resp.read().decode("utf-8"))

        for city in cities:
            city_name = city.get("city", "").lower()
            city_code = city.get("code", "")
            if keyword == city_name or keyword == city_name.rstrip("市区县旗州盟"):
                return city_code, "", city.get("city", "")
        return None
    except Exception:
        return None


# ============ 数据获取 ============

def fetch_weather(stationid):
    """从 API 获取天气数据"""
    url = f"{WEATHER_API}?stationid={stationid}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("code") != 0:
            print(f"API 返回错误: {data.get('msg', '未知错误')}", file=sys.stderr)
            sys.exit(1)
        return data.get("data", {})
    except urllib.error.URLError as e:
        print(f"网络请求失败: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print("API 返回数据格式异常", file=sys.stderr)
        sys.exit(1)


# ============ 格式化输出 ============

def format_real_weather(data):
    """格式化实时天气"""
    real = data.get("real", {})
    if not real:
        return "暂无实时天气数据"

    station = real.get("station", {})
    weather = real.get("weather", {})
    wind = real.get("wind", {})
    sun = real.get("sunriseSunset", {})

    lines = []
    lines.append("=" * 50)
    lines.append(f"📍 {station.get('province', '')} {station.get('city', '')} 实时天气")
    lines.append(f"🕐 数据发布时间: {real.get('publish_time', '未知')}")
    lines.append("-" * 50)

    # 温度
    temp = weather.get("temperature")
    feelst = weather.get("feelst")
    temp_diff = weather.get("temperatureDiff")

    temp_str = format_temperature(temp) if is_valid(temp) else "暂无数据"
    lines.append(f"🌡️  当前气温: {temp_str}")

    if is_valid(feelst):
        lines.append(f"🤒 体感温度: {format_temperature(feelst)}")

    if is_valid(temp_diff) and float(temp_diff) != 0:
        diff_sign = "+" if float(temp_diff) > 0 else ""
        lines.append(f"📉 温度变化: {diff_sign}{float(temp_diff):.1f}°C")

    # 湿度
    humidity = weather.get("humidity")
    if is_valid(humidity):
        lines.append(f"💧 相对湿度: {float(humidity):.0f}%")

    # 降水
    rain = weather.get("rain")
    if is_valid(rain):
        lines.append(f"🌧️  降水量: {float(rain):.1f}mm")

    # 风力
    wind_power = wind.get("power")
    if is_valid(wind_power):
        wind_direct = wind.get("direct")
        direct_str = wind_direct if is_valid(wind_direct) else ""
        wind_speed = wind.get("speed")
        speed_str = f" {float(wind_speed):.1f}m/s" if is_valid(wind_speed) else ""
        lines.append(f"🌬️  风: {direct_str}{wind_power}{speed_str}")

    # 日出日落
    sunrise = sun.get("sunrise")
    sunset = sun.get("sunset")
    if is_valid(sunrise) and is_valid(sunset):
        lines.append(f"🌅 日出: {sunrise.split(' ')[-1] if ' ' in sunrise else sunrise}")
        lines.append(f"🌇 日落: {sunset.split(' ')[-1] if ' ' in sunset else sunset}")

    # 舒适度
    rcomfort = weather.get("rcomfort")
    if is_valid(rcomfort):
        score = int(rcomfort)
        if score >= 80:
            comfort_level = "非常舒适"
        elif score >= 60:
            comfort_level = "比较舒适"
        elif score >= 40:
            comfort_level = "一般"
        elif score >= 20:
            comfort_level = "较不舒适"
        else:
            comfort_level = "不舒适"
        lines.append(f"😊 舒适度指数: {score} ({comfort_level})")

    lines.append("=" * 50)
    return "\n".join(lines)


def format_forecast(data):
    """格式化7天预报"""
    predict = data.get("predict", {})
    if not predict:
        return "暂无预报数据"

    detail = predict.get("detail", [])
    if not detail:
        return "暂无预报数据"

    station = predict.get("station", {})
    publish_time = predict.get("publish_time", "")

    lines = []
    lines.append("=" * 50)
    lines.append(f"📅 {station.get('city', '')} 7天天气预报")
    lines.append(f"🕐 预报发布时间: {publish_time}")
    lines.append("-" * 50)

    for day_data in detail:
        date = day_data.get("date", "")
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][dt.weekday()]
            date_display = f"{date} {weekday}"
        except ValueError:
            date_display = date

        lines.append(f"\n📆 {date_display}")

        day = day_data.get("day", {})
        night = day_data.get("night", {})

        # 白天天气
        day_weather = day.get("weather", {})
        day_info = day_weather.get("info")
        day_temp = day_weather.get("temperature")
        day_wind = day.get("wind", {})

        day_str_parts = []
        if is_valid(day_info):
            day_str_parts.append(f"天气: {day_info}")
        if is_valid(day_temp):
            day_str_parts.append(f"气温: {format_temperature(day_temp)}")
        wind_parts = []
        if is_valid(day_wind.get("direct")):
            wind_parts.append(day_wind["direct"])
        if is_valid(day_wind.get("power")):
            wind_parts.append(day_wind["power"])
        if wind_parts:
            day_str_parts.append(f"风: {' '.join(wind_parts)}")

        if day_str_parts:
            lines.append(f"  ☀️ 白天: {' | '.join(day_str_parts)}")

        # 夜间天气
        night_weather = night.get("weather", {})
        night_info = night_weather.get("info")
        night_temp = night_weather.get("temperature")
        night_wind = night.get("wind", {})

        night_str_parts = []
        if is_valid(night_info):
            night_str_parts.append(f"天气: {night_info}")
        if is_valid(night_temp):
            night_str_parts.append(f"气温: {format_temperature(night_temp)}")
        wind_parts = []
        if is_valid(night_wind.get("direct")):
            wind_parts.append(night_wind["direct"])
        if is_valid(night_wind.get("power")):
            wind_parts.append(night_wind["power"])
        if wind_parts:
            night_str_parts.append(f"风: {' '.join(wind_parts)}")

        if night_str_parts:
            lines.append(f"  🌙 夜间: {' | '.join(night_str_parts)}")

        # 降水量
        precip = day_data.get("precipitation")
        if is_valid(precip) and float(precip) > 0:
            lines.append(f"  🌧️  预计降水量: {float(precip):.1f}mm")

    lines.append("\n" + "=" * 50)
    return "\n".join(lines)


def format_hourly(data):
    """格式化逐小时数据"""
    passed = data.get("passedchart", [])
    if not passed:
        return "暂无逐小时数据"

    lines = []
    lines.append("=" * 50)
    lines.append("⏱️  过去24小时逐小时天气变化")
    lines.append("-" * 50)
    lines.append(f"{'时间':<20} {'气温':>6} {'湿度':>6} {'风向':<8} {'风速':>8} {'降水':>6}")
    lines.append("-" * 50)

    for entry in passed:
        time_str = entry.get("time", "")
        temp = entry.get("temperature")
        humidity = entry.get("humidity")
        wind_dir = entry.get("windDirection")
        wind_speed = entry.get("windSpeed")
        rain = entry.get("rain1h")

        try:
            dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
            short_time = dt.strftime("%m/%d %H:%M")
        except ValueError:
            short_time = time_str

        temp_str = f"{float(temp):.0f}°C" if is_valid(temp) else "-"
        humidity_str = f"{float(humidity):.0f}%" if is_valid(humidity) else "-"
        dir_str = wind_degree_to_direction(wind_dir) if is_valid(wind_dir) else "-"
        speed_str = f"{float(wind_speed):.1f}m/s" if is_valid(wind_speed) else "-"
        rain_str = f"{float(rain):.1f}mm" if is_valid(rain) and float(rain) > 0 else "-"

        lines.append(f"{short_time:<20} {temp_str:>6} {humidity_str:>6} {dir_str:<8} {speed_str:>8} {rain_str:>6}")

    lines.append("=" * 50)
    return "\n".join(lines)


# ============ 主入口 ============

def main():
    parser = argparse.ArgumentParser(description="全国天气查询工具 - 支持全国2500+城市")
    parser.add_argument("city", nargs="?", default="西安", help="城市名（如: 北京、上海、深圳、成都）")
    parser.add_argument(
        "--type", "-t",
        choices=["real", "forecast", "hourly", "all"],
        default="all",
        help="查询类型: real=实时天气, forecast=7天预报, hourly=逐小时, all=全部(默认)"
    )
    parser.add_argument(
        "--stationid", "-s",
        type=str,
        help="直接指定站点ID（跳过城市名查找）"
    )
    parser.add_argument(
        "--build-index", "-b",
        action="store_true",
        help="仅构建/更新站点索引"
    )
    parser.add_argument(
        "--search", "-S",
        type=str,
        help="搜索城市名，查看匹配结果"
    )
    args = parser.parse_args()

    # 索引构建模式
    if args.build_index:
        import subprocess
        subprocess.run([sys.executable, BUILD_SCRIPT, "--force"], check=True)
        return

    # 城市搜索模式
    if args.search:
        index = load_index()
        if not index:
            print("索引不存在，请先运行: python3 fetch_weather.py --build-index")
            return
        keyword = args.search.lower()
        matches = {k: v for k, v in index.get("city_lookup", {}).items() if keyword in k}
        if matches:
            print(f"找到 {len(matches)} 条匹配：")
            seen = set()
            for k, v in matches.items():
                key = f"{v['province']}{v['city']}{v['code']}"
                if key not in seen:
                    seen.add(key)
                    print(f"  {v['province']} {v['city']} → stationid={v['code']}")
        else:
            print(f"未找到匹配 '{args.search}' 的城市")
        return

    # 天气查询模式
    if args.stationid:
        stationid = args.stationid
        province, city = "", ""
    else:
        result = find_station(args.city)
        if not result:
            print(f"未找到城市 '{args.city}'，请检查城市名是否正确", file=sys.stderr)
            print(f"提示: 使用 --search 关键词 搜索可用城市", file=sys.stderr)
            print(f"提示: 使用 --build-index 更新站点索引", file=sys.stderr)
            sys.exit(1)
        stationid, province, city = result
        print(f"📍 查询城市: {province} {city} (stationid={stationid})")

    data = fetch_weather(stationid)

    output_parts = []

    if args.type in ("real", "all"):
        output_parts.append(format_real_weather(data))

    if args.type in ("forecast", "all"):
        output_parts.append(format_forecast(data))

    if args.type in ("hourly", "all"):
        output_parts.append(format_hourly(data))

    print("\n\n".join(output_parts))


if __name__ == "__main__":
    main()
