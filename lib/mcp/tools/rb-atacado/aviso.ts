import {lerConfig,configSchema} from './cliente';
import {textoRespostaRb} from './respostas';
type Deps={enabled:boolean;config:typeof lerConfig};
/** Somente avisos do motor, sem texto/condição financeira do modelo. */
export async function avisoRbVerificado(input:{organizationId:string;contactId:string;motivo:string},
 deps:Deps={enabled:process.env.RB_ATACADO_ENABLED==='1',config:lerConfig}){
 if(!deps.enabled)return null;
 try{
  const c=configSchema.parse(await deps.config());
  if(input.organizationId!==c.organization_id||input.contactId!==c.contact_id)return null;
  const resposta=input.motivo==='suspeita_de_opt_out'?'optout_respeitado':'atendimento_humano';
  return {resposta,body:textoRespostaRb(resposta)};
 }catch{return null;}
}
