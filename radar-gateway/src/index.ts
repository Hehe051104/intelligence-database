export default {
	async fetch(request: Request, env: Env): Promise<Response> {
		// 1. 零信任安保：验证请求头的暗号
		// 在测试阶段我们写死一个暗号，后续可用通过 CF 环境变量配置
		const EXPECTED_TOKEN = "SPEC-2026-SuperSecretKey"; 
		const authHeader = request.headers.get("Authorization");
		
		if (authHeader !== `Bearer ${EXPECTED_TOKEN}`) {
			return new Response(JSON.stringify({ error: "权限拒绝：暗号错误或未提供" }), { 
				status: 401, 
				headers: { "Content-Type": "application/json" } 
			});
		}

		// 确保只接收 POST 请求
		if (request.method !== "POST") {
			return new Response("Method Not Allowed", { status: 405 });
		}

		try {
			// 2. 解析来自外部（如你的 Python 爬虫）发送的情报数据
			const data: any = await request.json();
			const { title, summary, url, source_type, tags, importance_score, tech_difficulty, social_value } = data;

			// 验证必填项
			if (!title || !summary) {
				return new Response(JSON.stringify({ error: "缺失核心字段: title 或 summary" }), { status: 400 });
			}

			// 3. 特征提取：瞬间调用边缘 AI，将摘要文本转化为 768 维向量
			const embeddingResponse = await env.AI.run("@cf/baai/bge-base-en-v1.5", {
				text: [summary],
			});
			const vector = embeddingResponse.data[0];

			// 4. 生成唯一主键 ID (使用时间戳)
			const recordId = Date.now();

			// 5. 并发双写策略 (性能优化：不需要等待 A 写完再写 B)
			const dbPromise = env.DB.prepare(
				`INSERT INTO intel_records (id, title, summary, url, source_type, tags, importance_score, tech_difficulty, social_value) 
				 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
			)
			.bind(recordId, title, summary, url, source_type, tags, importance_score, tech_difficulty, social_value)
			.run();

			const vectorizePromise = env.VECTOR_INDEX.upsert([
				{
					id: recordId.toString(), // Vectorize 的 ID 必须是字符串
					values: vector,
					metadata: { title, tags } // 将标题和标签存入元数据，方便检索时直接调用
				}
			]);

			// 等待两方同时写入完成
			await Promise.all([dbPromise, vectorizePromise]);

			return new Response(JSON.stringify({ 
				success: true, 
				message: `[入库成功] 编号: ${recordId} 已同步至 D1 与 Vectorize` 
			}), {
				headers: { "Content-Type": "application/json" },
			});

		} catch (err: any) {
			return new Response(JSON.stringify({ error: `系统内部崩溃: ${err.message}` }), { 
				status: 500,
				headers: { "Content-Type": "application/json" }
			});
		}
	},
};