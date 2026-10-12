import { createHmac, timingSafeEqual } from 'node:crypto';
import { z } from 'zod';
const fotoSchema=z.object({
 org:z.uuid(),contact:z.uuid(),agent:z.uuid(),conversation:z.uuid(),job:z.uuid(),
 code:z.string().regex(/^\d{1,12}$/),path:z.string().max(250),
 mime:z.enum(['image/jpeg','image/png','image/webp']),body:z.string().min(1).max(1024),
 expira:z.number().int().positive(),
}).strict();
export type FotoAtestada=z.infer<typeof fotoSchema>;
function assinatura(data:FotoAtestada,key:string):string {
 return createHmac('sha256',key).update(JSON.stringify(fotoSchema.parse(data))).digest('hex');
}
export function assinarFoto(data:FotoAtestada,key:string) {
 const parsed=fotoSchema.parse(data);
 return {...parsed,sig:assinatura(parsed,key)};
}
export function conferirFoto(input:unknown,key:string,now:number):FotoAtestada {
 const signed=fotoSchema.extend({sig:z.string().regex(/^[a-f0-9]{64}$/)}).strict().parse(input);
 const {sig,...data}=signed;
 if(data.expira<=now||data.expira>now+120_000||
  !timingSafeEqual(Buffer.from(sig,'hex'),Buffer.from(assinatura(data,key),'hex')))throw new Error('foto não confirmada');
 const ext=data.mime==='image/jpeg'?'jpg':data.mime==='image/png'?'png':'webp';
 if(data.path!==data.org+'/'+data.conversation+'/mega-'+data.code+'-'+data.job+'.'+ext)throw new Error('foto não confirmada');
 return data;
}
