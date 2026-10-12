import type { SupabaseClient } from '@supabase/supabase-js';
import type pg from 'pg';
import { lerConfig, configSchema } from './cliente';
type Deps={enabled:boolean;config:typeof lerConfig};
/** Antes de roteamento/modelo: nesta organização de teste somente o contato privado.
 * Implantação exige confirmar que só o agente RB está publicado nesta organização.
 */
export async function confirmarEscopoRbAntesDaIA(pool:pg.Pool,
 input:{organizationId:string;conversationId:string},deps:Deps={
 enabled:process.env.RB_ATACADO_ENABLED==='1',config:lerConfig
}):Promise<boolean>{
 if(!deps.enabled)return true;
 try{
  const c=configSchema.parse(await deps.config());
  if(input.organizationId!==c.organization_id)return true;
  const {rows}=await pool.query<{contact_id:string;is_group:boolean;kind:string;is_blocked:boolean;is_anonymized:boolean;is_personal:boolean}>(
   'select cv.contact_id,cv.is_group,ct.kind,ct.is_blocked,ct.is_anonymized,ct.is_personal from conversations cv join contacts ct on ct.organization_id=cv.organization_id and ct.id=cv.contact_id where cv.organization_id=$1 and cv.id=$2',
   [input.organizationId,input.conversationId]);
  const row=rows[0];
  return Boolean(row&&row.contact_id===c.contact_id&&row.is_group===false&&
   row.kind!=='whatsapp_group'&&row.is_blocked===false&&row.is_anonymized===false&&row.is_personal===false);
 }catch{return false;}
}

export async function confirmarEscopoRbAntesDaIASupabase(admin:SupabaseClient,
 input:{organizationId:string;conversationId:string},deps:Deps={
 enabled:process.env.RB_ATACADO_ENABLED==='1',config:lerConfig
}):Promise<boolean>{
 if(!deps.enabled)return true;
 try{
  const c=configSchema.parse(await deps.config());
  if(input.organizationId!==c.organization_id)return true;
  const {data,error}=await admin.from('conversations')
   .select('contact_id,is_group,contacts:contact_id(kind,is_blocked,is_anonymized,is_personal)')
   .eq('organization_id',input.organizationId).eq('id',input.conversationId).maybeSingle();
  if(error||!data||data.contact_id!==c.contact_id||data.is_group!==false)return false;
  const contact=Array.isArray(data.contacts)?data.contacts[0]:data.contacts;
  return Boolean(contact&&contact.kind!=='whatsapp_group'&&contact.is_blocked===false&&
   contact.is_anonymized===false&&contact.is_personal===false);
 }catch{return false;}
}
