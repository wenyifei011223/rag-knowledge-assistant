# 工具链与参考资料

这一篇记录实现链路时用到的工具、接口兼容关系和权威文档入口。工具版本变化快，遇到行为不一致时优先查官方文档，不要依赖旧教程。

## DeepSeek API 的 SDK 兼容

DeepSeek 的 chat 接口兼容 OpenAI SDK 的消息格式和调用方式：请求里带 model、messages、temperature，响应里取 choices[0].message.content。这意味着用 ChatOpenAI 或直接用标准库发起 HTTP 请求都能接入，只需替换 base_url 和 API Key。

在轻量实现里可以直接用标准库的 urllib 发 POST 请求到接口地址，请求头带 Authorization Bearer Key，正文中指定模型名。这样做的好处是零依赖，便于在没有安装 SDK 的环境里跑通链路。调用失败要捕获异常并回退到本地抽取式回答，保证服务不中断。

API Key 只能通过环境变量传入，不能写进代码或提交到仓库。仓库的 .gitignore 里要包含 .env，并在 README 里写明配置方式。

## LangChain 文档与版本迁移

LangChain 1.x 之后，旧的 Retrievers 接口和部分链式调用写法有变化。排查迁移问题时，最可靠的资料是官方文档站 docs.langchain.com 的 What's new 和迁移指南，而不是搜索引擎里的旧博客。查问题时先看当前版本文档，再对照自己安装的版本确认 API 是否一致。

混合检索相关的 EnsembleRetriever 资料在 python.langchain.com 的 Retrievers 章节，里面说明了各路检索器如何加权、权重参数叫什么、返回结果怎么排序。用它之前要先确认它和当前安装的 langchain-community 版本匹配。

## Docker 入门与部署文档

Docker 官方文档的 Get Started 部分覆盖镜像构建、容器运行和端口映射，是部署环节的第一手资料。写 Dockerfile 时，把依赖安装层和代码复制层分开，可以显著加快重建速度。容器运行用 docker run 映射端口，健康检查通过服务暴露的 /health 接口完成。

如果索引文件需要更新，用数据卷把宿主目录挂进容器，避免每次重建镜像都重新入库。只读的固定知识库则可以直接把语料和索引打进镜像。

## 常用资料入口清单

LangChain 官方文档：docs.langchain.com，查版本变化、Retriever 接口和 Agent 抽象。Python 版 API 参考：python.langchain.com，查具体类的参数签名。DeepSeek 接口文档：平台控制台的文档页，查模型名、base_url 和限额。Docker 文档：docs.docker.com，查镜像构建与容器网络。bge 模型说明：模型仓库页面，查推荐的查询指令前缀和向量维度。

## 查资料的优先级

遇到行为不一致，按这个顺序排查：先看本地安装版本和文档版本是否一致；再看官方文档的对应章节；然后看项目的 CHANGELOG 或迁移指南；最后才看社区文章。社区文章适合理解思路，不适合作为 API 用法的依据，因为它们的时效性最差。

记录资料时要写清查的是哪个版本、哪一天查的。半年后回头看，这个信息能省掉大量重复搜索。
