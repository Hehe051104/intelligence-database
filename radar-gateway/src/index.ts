export interface Env {
	DB: D1Database;
	VECTOR_INDEX: VectorizeIndex;
	AI: any;
}

export default {
	async fetch(request: Request, env: Env): Promise<Response> {
		const corsHeaders = {
			"Access-Control-Allow-Origin": "*",
			"Access-Control-Allow-Methods": "GET, POST, OPTIONS",
			"Access-Control-Allow-Headers": "Content-Type, Authorization",
		};

		if (request.method === "OPTIONS") return new Response(null, { headers: corsHeaders });

		const url = new URL(request.url);

		// ==========================================
		// [GET 通道] 前端大屏获取数据
		// ==========================================
		if (request.method === "GET") {
			const queryText = url.searchParams.get("q"); 
			const interestFilter = url.searchParams.get("interest"); 

			try {
				if (!queryText) {
					let sql = "SELECT * FROM intel_records";
					let params: string[] = [];
					
					if (interestFilter && interestFilter !== 'ALL') {
						sql += " WHERE interest_topic = ?";
						params.push(interestFilter);
					}
					sql += " ORDER BY id DESC LIMIT 20";

					const { results } = await env.DB.prepare(sql).bind(...params).all();
					return new Response(JSON.stringify(results), { headers: { ...corsHeaders, "Content-Type": "application/json" } });
				}

				const embeddingResponse = await env.AI.run("@cf/baai/bge-base-en-v1.5", { text: [queryText] });
				const queryVector = embeddingResponse.data[0];
				
				const vecResults = await env.VECTOR_INDEX.query(queryVector, { topK: 12 });
				const matchIds = vecResults.matches.map((m: any) => m.id);

				if (matchIds.length === 0) return new Response(JSON.stringify([]), { headers: { ...corsHeaders, "Content-Type": "application/json" } });

				const placeholders = matchIds.map(() => "?").join(",");
				const { results } = await env.DB.prepare(`SELECT * FROM intel_records WHERE id IN (${placeholders})`).bind(...matchIds).all();

				let finalResults = results;
				if (interestFilter && interestFilter !== 'ALL') {
					finalResults = results.filter((r: any) => r.interest_topic === interestFilter);
				}

				const sortedResults = finalResults.sort((a: any, b: any) => matchIds.indexOf(a.id.toString()) - matchIds.indexOf(b.id.toString()));
				return new Response(JSON.stringify(sortedResults), { headers: { ...corsHeaders, "Content-Type": "application/json" } });

			} catch (err: any) {
				return new Response(JSON.stringify({ error: err.message }), { status: 500, headers: corsHeaders });
			}
		}

		// ==========================================
		// [POST 通道] 接收特工数据并双写落库
		// ==========================================
		if (request.method === "POST") {
			const EXPECTED_TOKEN = "SPEC-2026-SuperSecretKey"; 
			const authHeader = request.headers.get("Authorization");
			if (authHeader !== `Bearer ${EXPECTED_TOKEN}`) return new Response(JSON.stringify({ error: "权限拒绝" }), { status: 401, headers: corsHeaders });

			try {
				const data: any = await request.json();
				const { title, summary, url: linkUrl, source_type, tags, importance_score, tech_difficulty, social_value, interest_id } = data;

				if (!title || !summary) return new Response(JSON.stringify({ error: "缺失核心字段" }), { status: 400, headers: corsHeaders });

				const finalTopic = interest_id || "trending";
				const embeddingResponse = await env.AI.run("@cf/baai/bge-base-en-v1.5", { text: [summary] });
				const vector = embeddingResponse.data[0];
				const recordId = Date.now();

				const dbPromise = env.DB.prepare(
					`INSERT INTO intel_records (id, title, summary, url, source_type, tags, importance_score, tech_difficulty, social_value, interest_topic) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
				).bind(recordId, title, summary, linkUrl, source_type, tags, importance_score, tech_difficulty, social_value, finalTopic).run();

				const vectorizePromise = env.VECTOR_INDEX.upsert([{
					id: recordId.toString(), values: vector, metadata: { title, tags, source_type, interest_topic: finalTopic }
				}]);

				await Promise.all([dbPromise, vectorizePromise]);
				return new Response(JSON.stringify({ success: true }), { headers: corsHeaders });

			} catch (err: any) {
				return new Response(JSON.stringify({ error: err.message }), { status: 500, headers: corsHeaders });
			}
		}

		return new Response("Method Not Allowed", { status: 405, headers: corsHeaders });
	},

	// ==========================================
	// [定时器] 7天自动销毁过期数据 (Cron Job)
	// ==========================================
	async scheduled(event: ScheduledEvent, env: Env, ctx: ExecutionContext) {
		const sevenDaysAgo = Date.now() - (7 * 24 * 60 * 60 * 1000);
		
		const { results } = await env.DB.prepare(`SELECT id FROM intel_records WHERE id < ?`).bind(sevenDaysAgo).all();
		
		if (!results || results.length === 0) return;

		const expiredIds = results.map((row: any) => row.id.toString());

		try {
			// 先删向量，后删实体，保证一致性
			await env.VECTOR_INDEX.deleteByIds(expiredIds);
			const placeholders = expiredIds.map(() => "?").join(",");
			await env.DB.prepare(`DELETE FROM intel_records WHERE id IN (${placeholders})`).bind(...expiredIds).run();
			console.log(`🧹 肃清完成：销毁 ${expiredIds.length} 条数据。`);
		} catch (error) {
			console.error("清理任务崩溃:", error);
		}
	}
};