import { z } from "zod";
import { lerConfig, configSchema } from "./cliente";
import type { McpContext } from "../../types";

type Context = Pick<McpContext, "organizationId" | "contatoDoTurno" | "sourceJobId" | "supabase">;
const sku=z.string().regex(/^\d{1,12}$/);
const metadata=z.object({codigo:sku,nome:z.string().min(1).max(300),marca:z.string().max(100).nullable(),versao:z.enum(["EDP","EDT","Parfum","Elixir","Extrait de Parfum","EDC"]).nullable(),variante:z.literal("Eau Forte").nullable(),volume_ml:z.number().int().positive().max(5000).nullable(),apresentacao:z.enum(["kit","tester","refil","ambigua","não confirmada"])});
const fail=()=>({ok:false as const,code:"foto_nao_confirmada",message:"Não consegui confirmar a foto desta opção. Não envie outra imagem por aproximação."});
interface Deps {config:typeof lerConfig;fetch:typeof globalThis.fetch}
/** Called by the native send chain with trusted context, never as a free-form media tool. */
export async function prepararFotoMega(ctx:Context,input:{conversationId:string;codigo:string},deps:Deps={config:lerConfig,fetch:globalThis.fetch}) {
 try {
  const c=configSchema.parse(await deps.config());
  if (!c.enabled||ctx.organizationId!==c.organization_id||ctx.contatoDoTurno!==c.contact_id||!z.uuid().safeParse(input.conversationId).success||!z.uuid().safeParse(ctx.sourceJobId).success||!sku.safeParse(input.codigo).success)return fail();
  const contact=await ctx.supabase.from("contacts").select("id,kind,is_blocked,is_anonymized").eq("organization_id",ctx.organizationId).eq("id",c.contact_id).maybeSingle();
  if(contact.error||!contact.data||contact.data.id!==c.contact_id||contact.data.kind==="whatsapp_group"||contact.data.is_blocked!==false||contact.data.is_anonymized!==false)return fail();
  const conversation=await ctx.supabase.from("conversations").select("id,contact_id,is_group").eq("organization_id",ctx.organizationId).eq("id",input.conversationId).eq("contact_id",c.contact_id).maybeSingle();
  if(conversation.error||!conversation.data||conversation.data.id!==input.conversationId||conversation.data.contact_id!==c.contact_id||conversation.data.is_group!==false)return fail();
  const r=await deps.fetch("http://deskcommcrm-mega-vpn:40100/v1/foto",{method:"POST",redirect:"error",signal:AbortSignal.timeout(60_000),headers:{"Content-Type":"application/json",Authorization:`Bearer ${c.authorization_token}`},body:JSON.stringify({codigo:input.codigo})});
  if(!r.ok||!r.body)return fail();
  const label=r.headers.get("X-RB-Produto");
  if(!label||label.length>4096||!/^[A-Za-z0-9+/]+={0,2}$/.test(label))return fail();
  const product=metadata.parse(JSON.parse(Buffer.from(label,"base64").toString("utf8")));
  if(product.codigo!==input.codigo)return fail();
  const mime=r.headers.get("Content-Type")?.split(";")[0];
  if(!mime||!["image/jpeg","image/png","image/webp"].includes(mime))return fail();
  const reader=r.body.getReader();let total=0;const chunks:Uint8Array[]=[];
  try {while(true){const part=await reader.read();if(part.done)break;total+=part.value.byteLength;if(total>4_000_000){await reader.cancel();return fail();}chunks.push(part.value);}}finally{reader.releaseLock();}
  const bytes=Buffer.alloc(total);let offset=0;for(const part of chunks){bytes.set(part,offset);offset+=part.byteLength;}
  const valid=(mime==="image/jpeg"&&bytes.subarray(0,3).equals(Buffer.from([255,216,255])))||(mime==="image/png"&&bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10])))||(mime==="image/webp"&&bytes.subarray(0,4).toString()==="RIFF"&&bytes.subarray(8,12).toString()==="WEBP");
  if(!valid)return fail();
  const extension=mime==="image/jpeg"?"jpg":mime==="image/png"?"png":"webp";
  // Trusted tenant/conversation/job UUIDs only. Idempotent without upserting a different image.
  const path=`${ctx.organizationId}/${input.conversationId}/mega-${input.codigo}-${ctx.sourceJobId}.${extension}`;
  const upload=await ctx.supabase.storage.from("whatsapp-media").upload(path,bytes,{contentType:mime,upsert:false,cacheControl:"60"});
  if(upload.error&&String((upload.error as {statusCode?:string|number}).statusCode)!=="409")return fail();
  const description=[product.nome,`Concentração: ${product.versao??"a confirmar"}${product.variante?` (${product.variante})`:""}. Volume: ${product.volume_ml===null?"a confirmar":`${product.volume_ml} ml`}.`,`Apresentação: ${product.apresentacao}.`,`Disponibilidade informada pela loja; quantidade não informada. Valor depende de consulta e aprovação da RB Atacado.`].join("\n");
  return {ok:true as const,foto:{storagePath:path,mime},legenda:description};
 }catch{return fail();}
}
