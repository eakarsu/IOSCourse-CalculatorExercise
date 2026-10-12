'use strict';
(()=>{
const node=(tag,cls='',text)=>{const e=document.createElement(tag);e.className=cls;if(text!==undefined)e.textContent=text;return e;};
function inline(parent,text){
 const pattern=/(\*\*([^*]+)\*\*|`([^`]+)`|\[([^\]]+)\]\((https?:\/\/[^\s)]+)\))/g;let last=0;
 for(const m of text.matchAll(pattern)){parent.append(document.createTextNode(text.slice(last,m.index)));if(m[2])parent.append(node('strong','',m[2]));else if(m[3])parent.append(node('code','',m[3]));else{const a=node('a','',m[4]);a.href=m[5];a.target='_blank';a.rel='noopener noreferrer';parent.append(a);}last=m.index+m[0].length;}
 parent.append(document.createTextNode(text.slice(last)));
}
const readableLabel=value=>String(value).replace(/([a-z0-9])([A-Z])/g,'$1 $2').replace(/[_-]+/g,' ').replace(/^./,c=>c.toUpperCase());
function parsedJSON(text){try{return JSON.parse(text);}catch{return undefined;}}
function structuredValue(text){const value=parsedJSON(text);return value&&typeof value==='object'?value:undefined;}
function renderStructured(value,depth=0){
 const out=node('section','answer-structured');
 if(depth>20){out.append(node('p','','Additional nested detail is available in the copied or downloaded answer.'));return out;}
 if(Array.isArray(value)){
  if(!value.length){out.append(node('p','muted','No items supplied.'));return out;}
  const keys=[...new Set(value.flatMap(item=>item&&typeof item==='object'&&!Array.isArray(item)?Object.keys(item):[]))];
  if(keys.length&&keys.length<=8&&value.every(item=>item&&typeof item==='object'&&!Array.isArray(item)&&Object.values(item).every(v=>v===null||typeof v!=='object'))){
   const wrap=node('div','answer-table'),table=node('table'),head=node('thead'),row=node('tr');for(const key of keys)row.append(node('th','',readableLabel(key)));head.append(row);table.append(head);const body=node('tbody');for(const item of value){const row=node('tr');for(const key of keys){const cell=node('td');cell.append(renderStructured(item[key],depth+1));row.append(cell);}body.append(row);}table.append(body);wrap.append(table);out.append(wrap);
  }else{const list=node('ol','answer-items');for(const item of value){const entry=node('li');entry.append(renderStructured(item,depth+1));list.append(entry);}out.append(list);}return out;
 }
 if(value&&typeof value==='object'){
  const details=node('dl','answer-values');for(const [key,item] of Object.entries(value)){const entry=node('div');entry.append(node('dt','',readableLabel(key)));const content=node('dd');content.append(renderStructured(item,depth+1));entry.append(content);details.append(entry);}out.append(details);if(!Object.keys(value).length)out.append(node('p','muted','No details supplied.'));return out;
 }
 if(typeof value==='string'){
  const parsed=structuredValue(value.trim().replace(/^\x60\x60\x60(?:json)?\s*\n?([\s\S]*?)\n?\x60\x60\x60$/i,'$1'));
  if(parsed!==undefined)return renderStructured(parsed,depth+1);
  if(/\x60\x60\x60json/i.test(value))return renderAnswer(value);
 }
 const formatted=value===null||value===undefined?'Not supplied':typeof value==='boolean'?(value?'Yes':'No'):value===''?'(empty string)':String(value);for(const line of formatted.split('\n')){if(!line.trim())continue;const p=node('p');inline(p,line);out.append(p);}return out;
}
function renderAnswer(text){
 text=String(text??'');const out=node('div','answer-markdown'),whole=parsedJSON(text.trim());if(whole!==undefined){out.append(renderStructured(whole));return out;}
 const lines=text.replace(/\r\n/g,'\n').split('\n');let i=0;
 const cells=line=>line.trim().replace(/^\||\|$/g,'').split('|').map(x=>x.trim());
 while(i<lines.length){let line=lines[i];if(!line.trim()){i++;continue;}
  if(/^```/.test(line.trim())){const language=line.trim().slice(3).trim().toLowerCase(),code=[];i++;while(i<lines.length&&!/^```/.test(lines[i].trim()))code.push(lines[i++]);i++;const content=code.join('\n'),value=['json',''].includes(language)?parsedJSON(content):undefined;if(value!==undefined)out.append(renderStructured(value));else if(language==='json'){out.append(node('p','assistant-error','This structured section could not be read. Try generating the answer again.'));}else{const pre=node('pre');pre.append(node('code','',content));out.append(pre);}continue;}
  if(i+1<lines.length&&line.includes('|')&&cells(lines[i+1]).every(x=>/^:?-{3,}:?$/.test(x))){const wrap=node('div','answer-table'),table=node('table'),head=node('thead'),header=node('tr');for(const cell of cells(line)){const th=node('th');inline(th,cell);header.append(th);}head.append(header);table.append(head);i+=2;const body=node('tbody');while(i<lines.length&&lines[i].includes('|')&&lines[i].trim()){const row=node('tr');for(const cell of cells(lines[i++])){const td=node('td');inline(td,cell);row.append(td);}body.append(row);}table.append(body);wrap.append(table);out.append(wrap);continue;}
  const h=line.match(/^(#{1,6})\s+(.+)/);if(h){const heading=node('h'+Math.min(4,h[1].length+1));inline(heading,h[2]);out.append(heading);i++;continue;}
  if(/^\s*([-*+] |\d+[.)] )/.test(line)){const ordered=/^\s*\d+[.)] /.test(line),list=node(ordered?'ol':'ul');while(i<lines.length&&(ordered?/^\s*\d+[.)] /:/^\s*[-*+] /).test(lines[i])){const item=node('li');inline(item,lines[i++].replace(/^\s*(?:[-*+]|\d+[.)])\s+/,''));list.append(item);}out.append(list);continue;}
  const paragraph=node(line.startsWith('> ')?'blockquote':'p');inline(paragraph,line.replace(/^> /,''));out.append(paragraph);i++;
 }
 return out;
}
function readableAnswer(text){
 const read=element=>{
  if(element.nodeType===3)return element.textContent;
  if(element.tagName==='TABLE')return [...element.children].flatMap(section=>[...section.children]).map(row=>[...row.children].map(cell=>[...cell.childNodes].map(read).join('').trim()).join(' | ')).join('\n')+'\n\n';
  if(element.tagName==='DT')return element.textContent+':\n';
  if(element.tagName==='LI')return '- '+[...element.childNodes].map(read).join('').trim()+'\n';
  const content=[...element.childNodes].map(read).join('');
  return /^(P|H[1-6]|PRE|BLOCKQUOTE|DD)$/.test(element.tagName)?content.trim()+'\n\n':content;
 };
 return read(renderAnswer(text)).replace(/\n{3,}/g,'\n\n').trim();
}
 function mount({form,prompt,result,history,detail,refresh,list,read,call}){
  const examples=node('div','question-examples'),submit=form.querySelector('[type="submit"]'),cancel=node('button','','Cancel waiting'),status=node('p');cancel.type='button';cancel.hidden=true;status.setAttribute('role','status');
  const presets=[['Privacy review','Review this illustrative proposal: add optional AI assistance to the native local-first app. Assess data minimization, informed consent, access control, retention, and evidence. No production data is supplied. Identify missing facts, responsible owners to confirm, and a practical review checklist.'],['Quality review','Review this illustrative AI feature proposal for arithmetic integrity where applicable, factual accuracy, accessibility, and offline behavior. Treat examples as unverified test data. Recommend an evaluation plan with acceptance criteria, failure handling, and accountable human approval.'],['Launch review','Prepare an illustrative release-readiness review for optional AI assistance adjacent to this native app. Cover configuration, provider failure, authorization, audit evidence, rollback, and follow-up owners. Clearly distinguish recommended controls from controls actually verified by supplied evidence.']];
  let controller=null,version=0,historyVersion=0;
  function clearHistory(){historyVersion++;history.replaceChildren();detail.replaceChildren();}
  async function showSaved(id){const current=historyVersion;detail.replaceChildren(node('p','','Loading saved review…'));try{const {interaction}=await read(id);if(current!==historyVersion)return;const state=node('p','eyebrow',interaction.status+' · '+interaction.created_at);detail.replaceChildren(state);if(interaction.status==='SUCCEEDED')detail.append(renderAnswer(interaction.output_text??''));else detail.append(node('p','',interaction.error_code||'The review has not completed.'));}catch(error){if(current===historyVersion)detail.replaceChildren(node('p','assistant-error','Saved review unavailable: '+error.message));}}
  async function refreshHistory(){const current=++historyVersion;history.replaceChildren(node('p','','Loading saved reviews…'));detail.replaceChildren();try{const payload=await list();if(current!==historyVersion)return;const interactions=payload?.interactions;if(!Array.isArray(interactions))throw new Error('Invalid saved review list response.');history.replaceChildren();if(!interactions.length){history.append(node('p','muted','No saved reviews yet.'));return;}const items=node('ul','answer-items');for(const item of interactions){const entry=node('li'),button=node('button','',item.prompt.slice(0,90)+(item.prompt.length>90?'…':''));button.type='button';button.addEventListener('click',()=>showSaved(item.id));entry.append(button,node('span','muted',' '+item.status+' · '+item.created_at));items.append(entry);}history.append(items);}catch(error){if(current===historyVersion)history.replaceChildren(node('p','assistant-error','Saved reviews unavailable: '+error.message));}}
  refresh.addEventListener('click',refreshHistory);
  for(const [label,value] of presets){const button=node('button','',label);button.type='button';button.addEventListener('click',()=>{prompt.value=value;status.textContent='Complete example loaded. Review the question, then request the advisory.';prompt.focus();});examples.append(button);}
  form.prepend(examples);form.append(cancel,status,node('p','muted','This verification companion records provider attempts as immutable audit evidence. Cancel waiting stops this browser request; an upstream attempt may still finish.'));
  function lock(busy){submit.disabled=busy;prompt.disabled=busy;for(const b of examples.querySelectorAll('button'))b.disabled=busy;cancel.hidden=!busy;result.setAttribute('aria-busy',String(busy));}
  function stop(){if(!controller)return;version++;controller.abort();controller=null;lock(false);status.textContent='Waiting canceled. Your question is still here; the audit attempt is retained.';}
  cancel.addEventListener('click',stop);window.addEventListener('pagehide',stop);document.querySelector('#logout')?.addEventListener('click',stop);
  form.addEventListener('submit',async event=>{
   event.preventDefault();if(controller||!form.reportValidity())return;const request=new AbortController(),current=++version;controller=request;lock(true);status.textContent='Requesting the configured OpenRouter advisory…';
   try{const body=await call(request.signal);if(request.signal.aborted||current!==version)return;result.replaceChildren(node('p','eyebrow','OPENROUTER ADVISORY · REVIEW BEFORE USE'),renderAnswer(body.content));const receipt=node('dl','answer-values');for(const [label,value] of [['Model',body.providerReceipt?.upstreamModel||body.model],['Provider request',body.providerReceipt?.requestId],['Saved audit reference',body.interactionId]])if(value){const entry=node('div');entry.append(node('dt','',label),node('dd','',String(value)));receipt.append(entry);}result.append(receipt);status.textContent='Advisory received. Its provider evidence is retained.';refreshHistory();}
   catch(error){if(request.signal.aborted||current!==version)return;status.textContent='Advisory unavailable: '+error.message;}
   finally{if(controller===request){controller=null;lock(false);}}
  });
  window.AIReviewUI.refreshHistory=refreshHistory;
  window.AIReviewUI.clearHistory=clearHistory;
 }
 window.AIReviewUI={mount,renderAnswer};
})();
