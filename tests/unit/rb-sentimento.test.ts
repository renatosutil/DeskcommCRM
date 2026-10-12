import {afterEach,it,expect,vi} from "vitest";
import type {EventRow} from "@/lib/event-log/dispatcher";
vi.mock("@/lib/supabase/admin",()=>({createAdminClient:vi.fn(()=>({}))}));
vi.mock("@/lib/mcp/tools/rb-atacado/escopo",()=>({confirmarEscopoRbAntesDaIASupabase:vi.fn(async()=>false)}));
vi.mock("@/lib/ai/gateway-binding",()=>({resolverModeloDoPonto:vi.fn()}));
import {processSentiment} from "@/workers/ai-sentiment-worker";
import {resolverModeloDoPonto} from "@/lib/ai/gateway-binding";
import {confirmarEscopoRbAntesDaIASupabase} from "@/lib/mcp/tools/rb-atacado/escopo";
afterEach(()=>vi.unstubAllEnvs());
it("contato fora do teste não resolve nem consome modelo de sentimento",async()=>{
 vi.stubEnv("RB_ATACADO_ENABLED","1");
 const event={organization_id:"org-fixture",entity_id:"msg-fixture",payload:{conversation_id:"conversation-fixture"}} as unknown as EventRow;
 const r=await processSentiment(event);
 expect(r).toEqual({skipped:true,reason:"rb_fora_do_teste"});
 expect(confirmarEscopoRbAntesDaIASupabase).toHaveBeenCalled();
 expect(resolverModeloDoPonto).not.toHaveBeenCalled();
});
