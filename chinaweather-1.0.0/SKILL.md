---
name: china-weather
description: 查询全国任意城市的实时天气信息，包括当前气温、湿度、风力、日出日落、7天预报和逐小时数据。覆盖全国34个省份2529个气象站点。当用户询问任何中国城市的天气时，务必使用此技能，包括但不限于：北京天气、上海多少度、深圳会下雨吗、成都天气预报、杭州热不热、去广州要带伞吗、南京穿什么、武汉实时天气等。即使用户只是随口问"今天天气怎么样"，若上下文中暗示了某个中国城市，也应触发此技能。支持输入城市名（如"北京"、"上海"、"深圳"）或省份+城市（如"江苏南京"）。
---

# 全国天气查询技能

通过中央气象台（nmc.cn）公开 API 查询全国 2,529 个气象站点的天气数据，支持输入城市名即可查询，无需记住站点代码。

## 何时使用

任何与中国城市天气相关的提问，包括但不限于：
- "北京天气怎么样"
- "上海今天多少度"
- "深圳明天会下雨吗"
- "去成都要带伞吗"
- "哈尔滨现在冷不冷"
- "杭州穿什么衣服合适"
- "广州这周天气如何"
- "丽江实时天气"

## 数据覆盖

- **34 个省级行政区**：覆盖全部省份、直辖市、自治区、特别行政区
- **2,529 个气象站点**：从省会城市到区县站点
- **数据内容**：实时天气 + 7天预报 + 逐小时变化 + 温度趋势

## 使用方法

### 查询天气（主要用法）

```bash
# 查询指定城市天气（默认全部信息）
python3 /home/z/my-project/skills/china-weather/scripts/fetch_weather.py "城市名"

# 仅查实时天气
python3 /home/z/my-project/skills/china-weather/scripts/fetch_weather.py "北京" --type real

# 仅查7天预报
python3 /home/z/my-project/skills/china-weather/scripts/fetch_weather.py "上海" --type forecast

# 仅查逐小时数据
python3 /home/z/my-project/skills/china-weather/scripts/fetch_weather.py "深圳" --type hourly

# 直接使用站点ID查询（高级用法）
python3 /home/z/my-project/skills/china-weather/scripts/fetch_weather.py --stationid Wqsps
```

### 搜索城市

```bash
# 模糊搜索城市名，查看匹配的站点
python3 /home/z/my-project/skills/china-weather/scripts/fetch_weather.py --search "丽江"
```

### 更新站点索引

```bash
# 强制更新站点索引（一般不需要，索引会自动维护）
python3 /home/z/my-project/skills/china-weather/scripts/fetch_weather.py --build-index
```

## 城市名查找逻辑

脚本内置了智能城市名匹配：
1. **精确匹配**：输入"北京"直接匹配到北京市站点
2. **简写匹配**：输入"西安"可匹配"西安市"，去掉"市/县/区"等后缀
3. **省份+城市匹配**：支持"江苏南京"格式
4. **模糊匹配**：如果精确匹配失败，会进行包含关键词的模糊搜索
5. **动态查找**：如果本地索引未命中，会实时从 API 查找

## 回复用户时的注意事项

- 始终使用中文回复
- 根据用户的具体问题，有针对性地呈现相关信息，而非一次性堆砌所有数据
- 如果用户问"穿什么"，结合气温和天气状况给出穿衣建议
- 如果用户问"带伞吗"，关注降水概率和天气预报中的降雨信息
- 如果用户问"热不热/冷不冷"，关注体感温度和实际气温
- 对于"9999"等无效值，在回复中忽略不展示
- 数据来自中央气象台，可在回复中提一句数据来源增强可信度
- 如果用户问的城市找不到，建议用户尝试使用更完整的城市名或加上省份前缀
