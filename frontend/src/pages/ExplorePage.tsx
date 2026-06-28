import { Compass, Download, Star } from 'lucide-react'

export default function ExplorePage() {
  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <h2 className="text-xl font-bold text-gray-900">
            <Compass className="w-5 h-5 inline mr-2" />
            探索市场
          </h2>
          <p className="text-sm text-gray-500 mt-1">浏览和安装社区发布的 Agent、技能、工具等资产</p>
        </div>

        <div className="text-center py-16">
          <div className="w-16 h-16 bg-primary-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <Compass className="w-8 h-8 text-primary-500" />
          </div>
          <h3 className="text-lg font-semibold text-gray-700">LangSmith Hub 市场</h3>
          <p className="text-sm text-gray-400 mt-1 max-w-md mx-auto">
            通过 LangSmith Hub 连接全球 AI 社区。<br />
            发布您的资产，或安装来自其他团队的优秀作品。
          </p>
          <div className="mt-6 flex items-center justify-center gap-4">
            <div className="card text-center px-6 py-4">
              <div className="text-2xl font-bold text-primary-600">hub.pull()</div>
              <div className="text-xs text-gray-500 mt-1">安装资产</div>
            </div>
            <div className="card text-center px-6 py-4">
              <div className="text-2xl font-bold text-primary-600">hub.push()</div>
              <div className="text-xs text-gray-500 mt-1">发布资产</div>
            </div>
          </div>
          <p className="text-xs text-gray-400 mt-4">
            配置 LANGCHAIN_API_KEY 环境变量以启用 LangSmith Hub 集成
          </p>
        </div>
      </div>
    </div>
  )
}
