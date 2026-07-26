# 实时检查项目是否正常运行
- 按照项目描述。llm价格表在每日中国时间9:00-22:00间每隔1个小时定时刷新，请通过读取日志refresh.log来确定项目是否在正常刷新，如果发现有异常缺失则尝试解决。

# 项目改进方向-20260727
遵循最小改动原则，对项目进行如下改动：

将每个llm模型进行如下层级分类
- 来自不同平台，比如目前的openrouter，云雾AI两个平台
- 相同的平台下，不同的Provider，例如Anthropic、Deepseek、Google
- 相同平台、Provider下，推出的某个具体模型，如Anthropic旗下有claude-opus系列、claude-haiku系列、claude-sonnet系列。
- 某个具体模型又是不同在推出具体版本的，比如claude-opus-4.6到claude-opus-5都有。

项目对模型llm价格的分析，要求对于每一个特定的Provider的每一个具体模型，要求能够进行两个方面的对比。
- 一个是横向对比，对于同一个Provider、具体模型和版本，对比其在不同的平台的定价，将不同平台的价格随时间变化折线图放在一个坐标里。需要注意的是，同一个模型在opentouter和云雾AI平台上可能名字不同（例如在openrouter上是claude-3-haiku，在云雾AI平台上是claude-3-haiku-20240307，但是这里可以视为一个模型从而进行价格对比。
- 另一个是纵向对比，对于同一个平台的同一个Provider、具体模型，对比其不同版本（例如同样是openrouter的Anthropic的claude-opus，对比其不同版本opus-4.6、opus-4.7、opus-4.8、opus-5的价格），将同样模型但不同版本的价格随时间变化折线图放在一个坐标里。
