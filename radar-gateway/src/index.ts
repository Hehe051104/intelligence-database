export default {
	async fetch(request: Request, env: Env): Promise<Response> {
		// 1. 极其关键的跨域配置 (CORS)：没有这个，你的前端网页会被浏览器拦截
		const corsHeaders = {
			"Access-Control-Allow-Origin": "*",
			"Access-Control-Allow-Methods": "GET, POST, OPTIONS",
			"Access-Control-Allow-Headers": "Content-Type, Authorization",
		};

		// 处理浏览器的预检请求
		if (request.method === "OPTIONS") {
			return new Response(null, { headers: corsHeaders });
		}

		const url = new URL(request.url);

		// ==========================================
		// [新增] 前端大屏的专属通道 (GET: 语义检索 RAG)
		// ==========================================
		if (request.method === "GET") {
			const queryText = url.searchParams.get("q"); // 获取前端传来的搜索词

			try {
				// 场景 A：前端没有输入搜索词，直接返回最新入库的 10 条情报
				if (!queryText) {
					const { results } = await env.DB.prepare(
						"SELECT * FROM intel_records ORDER BY id DESC LIMIT 10"
					).all();
					return new Response(JSON.stringify(results), { 
						headers: { ...corsHeaders, "Content-Type": "application/json" } 
					});
				}

				// 场景 B：前端发起了搜索 -> 启动 RAG 向量检索
				// 1. 将用户的搜索词降维成 768 维特征向量
				const embeddingResponse = await env.AI.run("@cf/baai/bge-base-en-v1.5", {
					text: [queryText],
				});
				const queryVector = embeddingResponse.data[0];

				// 2. 在 Vectorize 时空矩阵中寻找最接近的 5 个情报 ID
				const vecResults = await env.VECTOR_INDEX.query(queryVector, { topK: 5 });
				const matchIds = vecResults.matches.map(m => m.id);

				if (matchIds.length === 0) {
					return new Response(JSON.stringify([]), { headers: { ...corsHeaders, "Content-Type": "application/json" } });
				}

				// 3. 拿着这些 ID 去 D1 数据库里把完整的文字记录提出来
				const placeholders = matchIds.map(() => "?").join(",");
				const sql = `SELECT * FROM intel_records WHERE id IN (${placeholders})`;
				const { results } = await env.DB.prepare(sql).bind(...matchIds).all();

				// 把结果按照向量相似度的顺序排好
				const sortedResults = results.sort((a: any, b: any) => matchIds.indexOf(a.id.toString()) - matchIds.indexOf(b.id.toString()));

				return new Response(JSON.stringify(sortedResults), { 
					headers: { ...corsHeaders, "Content-Type": "application/json" } 
				});

			} catch (err: any) {
				return new Response(JSON.stringify({ error: `检索系统崩溃: ${err.message}` }), { 
					status: 500, headers: corsHeaders 
				});
			}
		}

		// ==========================================
		// [保留] Python 特工的专属通道 (POST: 接收数据并双写)
		// ==========================================
		if (request.method === "POST") {
			const EXPECTED_TOKEN = "SPEC-2026-SuperSecretKey"; 
			const authHeader = request.headers.get("Authorization");
			
			if (authHeader !== `Bearer ${EXPECTED_TOKEN}`) {
				return new Response(JSON.stringify({ error: "权限拒绝" }), { status: 401, headers: corsHeaders });
			}

			try {
				const data: any = await request.json();
				const { title, summary, url: linkUrl, source_type, tags, importance_score, tech_difficulty, social_value } = data;

				if (!title || !summary) {
					return new Response(JSON.stringify({ error: "缺失核心字段" }), { status: 400, headers: corsHeaders });
				}

				const embeddingResponse = await env.AI.run("@cf/baai/bge-base-en-v1.5", { text: [summary] });
				const vector = embeddingResponse.data[0];
				const recordId = Date.now();

				const dbPromise = env.DB.prepare(
					`INSERT INTO intel_records (id, title, summary, url, source_type, tags, importance_score, tech_difficulty, social_value) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
				).bind(recordId, title, summary, linkUrl, source_type, tags, importance_score, tech_difficulty, social_value).run();

				const vectorizePromise = env.VECTOR_INDEX.upsert([{
					id: recordId.toString(), values: vector, metadata: { title, tags }
				}]);

				await Promise.all([dbPromise, vectorizePromise]);

				return new Response(JSON.stringify({ success: true, message: `入库成功` }), { headers: corsHeaders });

			} catch (err: any) {
				return new Response(JSON.stringify({ error: err.message }), { status: 500, headers: corsHeaders });
			}
		}

		return new Response("Method Not Allowed", { status: 405, headers: corsHeaders });
	},
};