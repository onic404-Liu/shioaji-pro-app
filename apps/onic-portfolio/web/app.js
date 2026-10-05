'use strict';
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money = (v, digits=2) => v == null || !Number.isFinite(Number(v)) ? '—' : Number(v).toLocaleString('zh-TW', {maximumFractionDigits:digits});
const signed = v => v == null ? '—' : (Number(v)>0?'+':'') + money(v);
const tone = v => Number(v)>0?'up':Number(v)<0?'down':'';
const timeText = v => v ? new Date(v*1000).toLocaleTimeString('zh-TW',{hour12:false,hour:'2-digit',minute:'2-digit',second:'2-digit'}) : '—';
const titles={cathay:['國泰未實現損益','台股與複委託的本機檔案快照，依來源及幣別呈現。'],overview:['庫存工作台','正式持倉、行情與 B15 追蹤。'],watch:['關注清單','把值得觀察的標的，留在你的視線裡。'],orders:['模擬委託','先確認內容，再送出每一筆委託。'],alerts:['價格提醒','訂好門檻，照自己的計畫追蹤。'],settings:['連線與金鑰','金鑰留在本機，帳務來源清楚可見。']};
const statuses={PendingSubmit:'傳送中',PreSubmitted:'預約中',Submitted:'已受理',Filled:'全部成交',PartFilled:'部分成交',Failed:'委託失敗',Cancelled:'已取消',Unknown:'結果未知'};
let page='overview', state=null, liveState=null, demo=false, busy=false, preview=null, seen=new Set(), initial=true, pollBusy=false, stopped=false;
let toastTimer, lastError='', sessionReady=false, selectedCode='', renderedContext='';
let token=sessionStorage.getItem('onic-session-token') || '';
function adoptLaunchToken(){const incoming=location.hash.slice(1);if(!/^[A-Za-z0-9_-]{40,}$/.test(incoming))return false;token=incoming;sessionStorage.setItem('onic-session-token',token);history.replaceState(null,'',location.pathname);return true;}
adoptLaunchToken();
window.addEventListener('hashchange',()=>{if(adoptLaunchToken()){sessionReady=false;lastError='';stopped=false;loginStatus('正在確認新的本機連線…');load();}});

function toast(text){$('#toast').textContent=text;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,4500);}
function banner(text,error=false){$('#banner').textContent=text;$('#banner').hidden=!text;$('#banner').classList.toggle('error',error);}
function ask(text){return new Promise(resolve=>{const dialog=$('#action-dialog');$('#action-description').textContent=text;$('#action-back').onclick=()=>{dialog.returnValue='cancel';dialog.close();};$('#action-yes').onclick=()=>{dialog.returnValue='yes';dialog.close();};dialog.onclose=()=>resolve(dialog.returnValue==='yes');dialog.returnValue='cancel';dialog.showModal();});}
async function request(route,data){
 if(!token)throw Error('請用「啟動投資簿」開啟此介面，建立本機連線。');
 const options={headers:{Authorization:'Bearer '+token},cache:'no-store'};
 if(data!==undefined){options.method='POST';options.headers['Content-Type']='application/json';options.body=JSON.stringify(data);}
 let response;try{response=await fetch('/api/'+route,options);}catch{throw Error('本機服務沒有回覆。若剛送出委託，請先核對回報，勿直接重送。');}
 let result;try{result=await response.json();}catch{throw Error('本機服務沒有回覆。請重新啟動投資簿。');}
 if(response.status===401){sessionReady=false;loginStatus('這個分頁的本機連線已失效。請關閉舊投資簿分頁與服務視窗，再雙擊「啟動投資簿.cmd」。',true);}
 if(!response.ok)throw Error(result.error||'操作未完成。');
 return result;
}
function loginStatus(text,error=false){$('#login-status').textContent=text;$('#login-status').hidden=!text;$('#login-status').classList.toggle('error',error);$('#login').disabled=busy||!sessionReady||demo;}
function setBusy(value){busy=value;document.body.classList.toggle('busy',value);$('#login').disabled=value||!sessionReady||demo;const canTrade=state?.connected&&state.profile==='simulation'&&!state.inventory_only&&!demo;$('#order-preview').disabled=value||!canTrade;$('#refresh-orders').disabled=value||!canTrade;for(const id of ['refresh','refresh-quotes'])$('#'+id).disabled=value||!state?.connected||demo;}
async function act(route,data={},message){
 if(demo)throw Error('目前為設計預覽；請先退出預覽，再操作 API 或儲存資料。');
 if(busy)throw Error('前一個操作尚未完成。');
 lastError='';setBusy(true);
 try{const result=await request(route,data);if('connected' in result){liveState=result;state=result;render();}else{liveState=await request('state');state=liveState;render();}if(message)toast(message);return result;}
 catch(error){lastError=error.message;throw error;}
 finally{setBusy(false);}
}
async function load(){
 if(pollBusy||busy||stopped)return;
 pollBusy=true;
 try{liveState=await request('state');const recovered=!sessionReady;sessionReady=true;if(recovered)loginStatus('本機服務已就緒。請輸入金鑰連線。');if(!demo){state=liveState;render();notifyEvents(state.events);loadCathay();}}
 catch(error){banner(error.message,true);if(!sessionReady)loginStatus('本機服務尚未就緒或連線已失效。請關閉舊投資簿分頁與服務視窗，再雙擊「啟動投資簿.cmd」。',true);}
 finally{pollBusy=false;}
}
function notifyEvents(events){
 if(initial){events.forEach(e=>seen.add(e.id));initial=false;return;}
 for(const event of events){if(seen.has(event.id))continue;seen.add(event.id);toast(event.text);if('Notification' in window && Notification.permission==='granted')new Notification('投資簿價格提醒',{body:event.text});}
}
function nav(target){page=target==='orders'?'overview':target;$$('.page').forEach(p=>p.hidden=p.id!==page);$$('[data-page]').forEach(b=>{b.classList.toggle('active',b.dataset.page===page);b.setAttribute('aria-current',b.dataset.page===page?'page':'false');});$('#page-title').textContent=titles[page][0];$('#page-description').textContent=titles[page][1];$('#refresh').hidden=page!=='overview';if(state)render();window.scrollTo({top:0,behavior:'instant'});}
function quoteTime(q){if(!q)return '尚無行情';if(demo)return '虛構示範';const age=Date.now()/1000-q.at;return `${timeText(q.at)}<small class="${age>90?'stale':''}">${age>90?'逾 90 秒無更新':esc(q.source)} · 接收時間</small>`;}
function nameCell(symbol,name){return `<span>${esc(name||symbol)}</span><small>${esc(symbol)}</small>`;}
function eventsHTML(events){return events.length?[...events].reverse().map(e=>`<div class="event"><p>${esc(e.text)}</p><small>${demo?'虛構示範':timeText(e.at)} · NT$ ${money(e.price)} · ${signed(e.pct)}%</small></div>`).join(''):'<div class="event"><p class="muted">目前沒有觸發提醒。</p><small>有新提醒時會顯示在這裡。</small></div>';}
function render(){
 if(!state)return;
 const context=JSON.stringify([demo,state.connected,state.profile,state.accounts[state.account_index]]);
 if(context!==renderedContext){renderedContext=context;selectedCode='';const f=$('#order-form');f.elements.code.value='';f.elements.price.value='';estimate();}
 const connected=state.connected;
 $('#connection-status').textContent=demo?'設計預覽':connected?(state.profile==='simulation'?'模擬環境已連線':'正式查詢已連線'):'尚未連線';
 $('#connection-dot').className='dot'+(demo?' demo':connected?' connected':'');
 const source=state.fixture?'離線假服務 · 非永豐連線':demo?'所有數字均為虛構示範':connected?(state.profile==='simulation'?'模擬帳務 · 非真實庫存':'正式帳務 · 交易已封鎖'):'沒有載入帳務資料';
 $('#source-label').textContent=source;$('#footer-source').textContent=source;
 $('#connect-shortcut').hidden=connected;$('#disconnect').hidden=!connected;$('#account').disabled=!connected||demo;
 const options=state.accounts.length?state.accounts.map((a,i)=>`<option value="${i}">${esc(a)}</option>`).join(''):'<option>尚未選擇帳戶</option>';
 if($('#account').innerHTML!==options)$('#account').innerHTML=options;
 $('#account').value=state.accounts.length?String(state.account_index):'';
 $('#demo').textContent=demo?'退出設計預覽':'查看設計預覽';
 if(lastError)banner(lastError,true);
 else if(state.fixture)banner('離線操作測試：使用隔離的假服務驗證介面流程，沒有永豐連線或真實金鑰。');
 else if(demo)banner('設計預覽：所有帳務、行情及提醒均為虛構示範。API 操作與儲存已停用。');
 else if(state.positions_error||state.quote_error)banner([state.positions_error,state.quote_error].filter(Boolean).join(' '),true);
 else if(connected&&state.profile==='simulation')banner('模擬帳務不代表真實持股。完成模擬下單後，仍須確認永豐的 API 測試審核結果。');
 else banner('');
 let total=0,complete=state.positions_at!==null;
 for(const p of state.positions){const price=state.quotes[p.code]?.price??p.last_price;if(price==null||p.quantity==null)complete=false;else total+=Number(price)*Number(p.quantity);}
 $('#total-value').textContent=complete?money(total,0):'—';
 const pnls=state.positions.map(p=>p.pnl);
 const pnl=state.positions_at!==null&&pnls.every(p=>p!=null)?pnls.reduce((a,b)=>a+Number(b),0):null;
 $('#total-pnl').textContent=pnl==null?'—':signed(pnl);$('#total-pnl').className=tone(pnl);
 $('#holding-count').textContent=state.positions_at!==null?state.positions.length:'—';$('#watch-count').innerHTML=`${state.watch.length} <small>檔</small>`;$('#alert-count').textContent=`${state.alerts.length} 組提醒規則`;
 const search=$('#search').value.trim().toLowerCase();
 const filtered=state.positions.filter(p=>String(p.code).includes(search)||(state.quotes[p.code]?.name||'').toLowerCase().includes(search));
 $('#positions-body').innerHTML=filtered.map(p=>{const q=state.quotes[p.code];return `<tr data-code="${esc(p.code)}" tabindex="0" aria-label="將 ${esc(p.code)} 查看持倉明細"><td>${nameCell(p.code,q?.name)}</td><td>${money(p.quantity,0)}<small>${esc(p.direction||'')} · ${esc(p.cond||'')}</small></td><td>${money(p.price)}</td><td>${money(q?.price??p.last_price)}<small class="${tone(q?.change)}">${q?signed(q.change)+'%':'帳務最近價'}</small></td><td class="${tone(p.pnl)}">${signed(p.pnl)}</td><td>${quoteTime(q)}</td></tr>`;}).join('');
 $('#positions-empty').hidden=filtered.length>0;
 const empty=$('#positions-empty');
 if(state.positions_at!==null){empty.querySelector('h3').textContent=search?'沒有符合的標的。':'目前帳戶沒有庫存。';empty.querySelector('p').textContent=search?'試試其他名稱或代號。':'這是本次帳務查詢回覆的結果；可與永豐官方 App 核對。';empty.querySelector('button').hidden=true;}
 else{empty.querySelector('h3').textContent=state.positions_error?'尚未取得庫存。':'先連線，再看你的持股。';empty.querySelector('p').textContent=state.positions_error||'登入正式環境後才會載入帳務。查詢失敗會保留上次成功資料。';empty.querySelector('button').hidden=connected;}
 $('#positions-time').textContent=demo?'虛構庫存示範':state.positions_at?`庫存查詢 ${timeText(state.positions_at)}${state.positions_error?' · 保留上次結果':''}`:'庫存尚未更新';
 $('#event-count').textContent=state.events.length;$('#recent-events').innerHTML=eventsHTML(state.events.slice(-3));$('#all-events').innerHTML=eventsHTML(state.events);
 $('#watch-body').innerHTML=state.watch.map(w=>{const q=state.quotes[w.code];return `<tr><td>${nameCell(w.code,q?.name||w.name)}</td><td>${money(q?.price)}</td><td class="${tone(q?.change)}">${q?signed(q.change)+'%':'—'}</td><td>${esc(w.note)}</td><td>${quoteTime(q)}</td><td><button class="text-button" data-remove-watch="${esc(w.code)}" aria-label="移除 ${esc(w.code)} 關注">移除</button></td></tr>`;}).join('');$('#watch-empty').hidden=state.watch.length>0;
 $('#alerts-body').innerHTML=state.alerts.map(a=>{const q=state.quotes[a.code],pct=q?(q.price/a.base-1)*100:null;return `<tr><td>${nameCell(a.code,q?.name)}</td><td>${money(a.base)}</td><td>${money(a.base*(1-a.pct/100))}<small>−${money(a.pct)}%</small></td><td>${money(a.base*(1+a.pct/100))}<small>+${money(a.pct)}%</small></td><td class="${tone(pct)}">${pct==null?'—':signed(pct)+'%'}</td><td>${money(a.cooldown/60)} 分鐘</td><td><button class="text-button" data-remove-alert="${esc(a.id)}">刪除</button></td></tr>`;}).join('');$('#alerts-empty').hidden=state.alerts.length>0;
 $('#orders-body').innerHTML=[...state.orders].reverse().map(o=>`<tr><td>${nameCell(o.code,o.name)}<small class="${o.action==='Buy'?'up':'down'}">${o.action==='Buy'?'買進':'賣出'}</small></td><td>${money(o.price)}</td><td>${money(o.quantity,0)}<small>已成交 ${money(o.filled,0)} 張</small></td><td><span class="badge ${['Unknown','PendingSubmit'].includes(o.status)?'warning':o.status==='Failed'?'red':'green'}">${esc(statuses[o.status]||o.status)}</span></td><td>${['Submitted','PartFilled','PreSubmitted'].includes(o.status)?`<button class="text-button" data-cancel="${esc(o.id)}">撤銷</button>`:''}</td></tr>`).join('');$('#orders-empty').hidden=state.orders.length>0;$('#orders-time').textContent=demo?'虛構委託示範':state.report_at?'最近回報／查詢 '+timeText(state.report_at):'尚未取得回報';
 const canTrade=connected&&state.profile==='simulation'&&!state.inventory_only&&!demo;
 $('#order-preview').disabled=!canTrade||busy;$('#refresh-orders').disabled=!canTrade||busy;
 $('#order-warning').textContent=canTrade?'目前帳戶：'+state.accounts[state.account_index]+'。僅可送出模擬單。':connected&&!demo?'目前是正式查詢環境。請切換模擬測試金鑰後下單。':'請使用模擬測試金鑰連線，才能建立委託。';
 $('#refresh').disabled=!connected||demo||busy;$('#refresh-quotes').disabled=!connected||demo||busy;
 for(const p of ['simulation','readonly']){$('#vault-'+p).textContent=state.saved[p]?'已保存 · Windows 保護':'未保存';$(`[data-delete-key="${p}"]`).disabled=!state.saved[p]||demo;}
 renderCathay();
 renderTerminal(true);
 profileFields();
}
function profileFields(){const f=$('#connect-form'),profile=f.elements.profile.value,saved=!!state?.saved[profile];$('#saved-status').textContent=saved?'已保存，可直接使用':'此用途尚未保存';$('#use-saved').disabled=!saved||demo;if(!saved)$('#use-saved').checked=false;$('#credential-fields').hidden=$('#use-saved').checked;f.elements.key.required=!$('#use-saved').checked;f.elements.secret.required=!$('#use-saved').checked;f.elements.signed.required=profile==='simulation';$('#login').textContent=profile==='simulation'?'連線到模擬環境':'連線到正式查詢環境';}
function estimate(){const f=$('#order-form');const amount=Number(f.elements.price.value)*Number(f.elements.quantity.value)*1000;$('#order-amount').textContent=amount>0&&Number.isFinite(amount)?'NT$ '+money(amount,0):'—';}
function draft(symbol){selectedCode=symbol;nav('overview');$('#order-form').elements.code.value=symbol;const q=state.quotes[symbol];$('#order-form').elements.price.value=q?.price??'';estimate();renderTerminal();}
function renderTerminal(selectDefault=false){
 if(!state)return;
 if(selectDefault&&!selectedCode){selectedCode=state.positions[0]?.code||state.watch[0]?.code||'';const f=$('#order-form');f.elements.code.value=selectedCode;f.elements.price.value=state.quotes[selectedCode]?.price??'';estimate();}
 const item=(code,name)=>{const q=state.quotes[code];return `<button class="symbol-row ${selectedCode===code?'selected':''}" data-select-symbol="${esc(code)}" aria-pressed="${selectedCode===code}"><span><strong>${esc(code)}</strong><small>${esc(q?.name||name||code)}</small></span><span><strong>${money(q?.price)}</strong><small class="${tone(q?.change)}">${q?signed(q.change)+'%':'尚無行情'}</small></span></button>`;};
 $('#desk-watch').innerHTML=state.watch.map(w=>item(w.code,w.name)).join('')||'<p class="list-note">尚無關注標的。可從編輯清單新增。</p>';
 $('#desk-holdings').innerHTML=state.positions.map(p=>item(p.code)).join('')||'<p class="list-note">連線後顯示持有標的。</p>';
 const q=state.quotes[selectedCode],p=state.positions.find(p=>p.code===selectedCode),a=state.alerts.find(a=>a.code===selectedCode);
 $('#selected-name').textContent=q?.name||selectedCode||'選擇一檔股票';$('#selected-code').textContent=selectedCode||'由左側清單或庫存點選';
 $('#selected-price').textContent=money(q?.price);$('#selected-price').className=tone(q?.change);
 $('#selected-change').textContent=q?signed(q.change)+'%':'尚無報價';$('#selected-change').className=tone(q?.change);
 $('#selected-source').textContent=demo?'虛構示範':q?timeText(q.at)+' · '+q.source:'尚無行情';
 $('#selected-quantity').textContent=money(p?.quantity,0);$('#selected-cost').textContent=money(p?.price);$('#selected-pnl').textContent=signed(p?.pnl);$('#selected-pnl').className=tone(p?.pnl);
 $('#selected-range').textContent=a?money(a.base*(1-a.pct/100))+' – '+money(a.base*(1+a.pct/100)):'尚未設定';
 $('#b15-symbol').textContent=p?((q?.name||p.code)+' · '+p.code):'請選擇持有標的';$('#b15-quantity').textContent=p?money(p.quantity,0)+' 股':'—';
 $('#selected-note').textContent=state.watch.find(w=>w.code===selectedCode)?.note||'顯示最近報價。歷史走勢尚未接入。';
 $$('tr[data-code]').forEach(r=>r.classList.toggle('selected',r.dataset.code===selectedCode));
}
function formData(form){return Object.fromEntries(new FormData(form));}
function demoData(){const at=Date.now()/1000;return {connected:false,profile:null,accounts:[],account_index:0,saved:liveState?.saved||{simulation:false,readonly:false},positions_at:at,positions_error:null,quote_error:null,positions:[{code:'2330',quantity:1000,price:950,last_price:1020,pnl:70000,direction:'Buy',cond:'Cash'},{code:'0050',quantity:2000,price:48,last_price:52.8,pnl:9600,direction:'Buy',cond:'Cash'},{code:'2890',quantity:3000,price:28,last_price:27.6,pnl:-1200,direction:'Buy',cond:'Cash'}],quotes:{'2330':{name:'台積電',price:1020,change:1.49,at,source:'虛構示範'},'0050':{name:'元大台灣50',price:52.8,change:0.76,at,source:'虛構示範'},'2890':{name:'永豐金',price:27.6,change:-0.72,at,source:'虛構示範'},'2308':{name:'台達電',price:390,change:2.63,at,source:'虛構示範'}},watch:[{code:'2308',name:'台達電',note:'追蹤季度營運變化（示範）'},{code:'2330',name:'台積電',note:'檢視持股集中度（示範）'}],alerts:[{id:'demo-alert',code:'2330',base:920,pct:10,cooldown:600,enabled:true}],orders:[{id:'demo-order',code:'2890',name:'永豐金',action:'Buy',quantity:1,filled:1,price:28,status:'Filled'}],events:[{id:'demo-event',at,code:'2330',text:'2330 已達預設上限，請檢視追蹤計畫。（虛構示範）',price:1020,pct:10.87}],report_at:at};}

$$('[data-page]').forEach(b=>b.addEventListener('click',()=>nav(b.dataset.page)));
$('.brand').addEventListener('click',e=>{e.preventDefault();nav('overview');});
$$('[data-open-settings]').forEach(b=>b.addEventListener('click',()=>nav('settings')));$$('[data-open-alerts]').forEach(b=>b.addEventListener('click',()=>nav('alerts')));
$('#connect-shortcut').addEventListener('click',()=>nav('settings'));
$('#search').addEventListener('input',render);
$('#order-form').addEventListener('input',()=>{estimate();selectedCode=$('#order-form').elements.code.value.trim();renderTerminal();});
$('#connect-form').addEventListener('change',profileFields);
$('#demo').addEventListener('click',()=>{if(liveState?.connected){toast('請先登出 API，再查看設計預覽。');return;}demo=!demo;state=demo?demoData():liveState;render();});
$('#connect-form').addEventListener('submit',async e=>{e.preventDefault();const f=e.currentTarget,d=formData(f);d.use_saved=f.elements.use_saved.checked;d.save=f.elements.save.checked;d.signed=f.elements.signed.checked;try{if(!sessionReady)throw Error('本機連線已失效，請重新用啟動檔開啟。');loginStatus('正在登入永豐正式查詢環境，請稍候…');await act('connect',d,'API 登入完成，請核對帳戶與資料來源。');f.elements.key.value='';f.elements.secret.value='';loginStatus('登入完成，金鑰輸入欄已清空。');initial=true;nav('overview');}catch(error){loginStatus(error.message,true);banner(error.message,true);}});
$('#disconnect').addEventListener('click',async()=>{try{await act('disconnect',{},'已登出，停止報價追蹤。');initial=true;}catch(e){toast(e.message);}});
$('#account').addEventListener('change',async e=>{try{await act('account',{index:Number(e.target.value)},'已切換證券帳戶。');}catch(e){toast(e.message);}});
$('#refresh').addEventListener('click',async()=>{try{await act('positions',{},'查詢已回覆；請核對更新時間與失敗提示。');}catch(e){toast(e.message);}});
$('#refresh-quotes').addEventListener('click',async()=>{try{await act('quotes',{},'已請求更新行情。');}catch(e){toast(e.message);}});
$('#refresh-orders').addEventListener('click',async()=>{try{await act('orders/refresh',{},'委託回報已查詢。');}catch(e){toast(e.message);}});
$('#watch-form').addEventListener('submit',async e=>{e.preventDefault();try{await act('watch/add',formData(e.target),'已保存關注標的。');e.target.reset();}catch(e){toast(e.message);}});
$('#alert-form').addEventListener('submit',async e=>{e.preventDefault();const d=formData(e.target);d.cooldown=Number(d.cooldown)*60;try{await act('alerts/save',d,'價格提醒規則已保存並啟用。');}catch(e){toast(e.message);}});
$('#order-form').addEventListener('submit',async e=>{e.preventDefault();try{preview=await act('orders/preview',formData(e.target));$('#confirm-account').textContent='證券帳戶 '+state.accounts[state.account_index];const items=[['標的',preview.name+' '+preview.code],['買賣別',preview.action==='Buy'?'買進':'賣出'],['每股限價','NT$ '+money(preview.price)],['數量',preview.quantity+' 張（'+money(preview.quantity*1000,0)+' 股）'],['預估金額','NT$ '+money(preview.amount,0)]];$('#confirm-details').innerHTML=items.map(([k,v])=>`<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('');$('#confirm-submit').disabled=false;$('#confirm-dialog').showModal();}catch(e){toast(e.message);}});
$('#cancel-preview').addEventListener('click',()=>$('#confirm-dialog').close());
$('#confirm-submit').addEventListener('click',async()=>{if(!preview)return;$('#confirm-submit').disabled=true;const id=preview.id;preview=null;try{await act('orders/submit',{id},'模擬下單已呼叫。請查詢回報確認最終狀態。');$('#confirm-dialog').close();setTimeout(()=>load(),1500);}catch(e){$('#confirm-dialog').close();banner(e.message,true);toast(e.message);}});
document.addEventListener('click',async e=>{const symbol=e.target.closest('[data-select-symbol]');if(symbol){draft(symbol.dataset.selectSymbol);return;}const row=e.target.closest('tr[data-code]');if(row){draft(row.dataset.code);return;}try{const w=e.target.closest('[data-remove-watch]'),a=e.target.closest('[data-remove-alert]'),c=e.target.closest('[data-cancel]'),k=e.target.closest('[data-delete-key]');if(w)await act('watch/remove',{code:w.dataset.removeWatch},'已移除關注。');if(a)await act('alerts/remove',{id:a.dataset.removeAlert},'已刪除提醒規則。');if(c&&await ask('確認撤銷這筆模擬委託？'))await act('orders/cancel',{id:c.dataset.cancel},'已提出模擬撤單，請更新回報確認。');if(k&&await ask('刪除 Windows 中保存的這組金鑰？現有登入仍會維持，直到登出。'))await act('credentials/delete',{profile:k.dataset.deleteKey},'已刪除本機保存的金鑰。');}catch(e){toast(e.message);}});
document.addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&e.target.matches('tr[data-code]')){e.preventDefault();draft(e.target.dataset.code);}});
$('#enable-notifications').addEventListener('click',async()=>{if(!('Notification' in window)){toast('此瀏覽器不支援桌面通知，仍可使用畫面提醒。');return;}const permission=await Notification.requestPermission();toast(permission==='granted'?'瀏覽器通知已開啟；請保持服務與頁面開啟。':'未開啟通知；仍會顯示畫面提醒。');});
$('#shutdown').addEventListener('click',async()=>{if(demo){toast('請先退出設計預覽。');return;}if(!await ask('結束本機服務？行情與提醒會停止。'))return;try{await request('shutdown',{});stopped=true;liveState.connected=false;liveState.profile=null;state=liveState;render();$('#connection-status').textContent='本機服務已結束';banner('本機服務已結束。請關閉此頁；下次用啟動檔重新開啟。');}catch(e){toast(e.message);}});
setInterval(()=>{$('#clock').textContent=new Date().toLocaleDateString('zh-TW',{month:'long',day:'numeric',weekday:'short'});},1000);
setInterval(load,2500);
load();

let cathayReport={sources:[]},cathayBusy=false,cathayError='';
function cathayDate(value){return value?new Date(value*1000).toLocaleString('zh-TW',{hour12:false}):'—';}
function reportSources(){if(demo)return [{kind:'tw',label:'國泰台股',file:'虛構台股示範',modified_at:null,rows:[{name:'示範標的 A',currency:'TWD',quantity:1000,average:40,price:42,cost:40000,market_value:42000,pnl:2000,return_pct:5}],totals:[{currency:'TWD',pnl:2000,count:1}]},{kind:'overseas',label:'國泰複委託',file:'虛構複委託示範',modified_at:null,rows:[{name:'DEMO 示例標的',market:'示範市場',currency:'USD',quantity:10,average:100,price:105,cost:1000,market_value:1050,pnl:50,return_pct:5}],totals:[{currency:'USD',pnl:50,count:1}]}];return cathayReport.sources||[];}
function renderCathay(){
 const sources=reportSources(),filter=$('#cathay-filter').value,search=$('#cathay-search').value.trim().toLowerCase();
 const failed=!!cathayError||sources.some(s=>s.error);
 $('#cathay-summary-values').innerHTML=(sources.flatMap(s=>s.totals.map(t=>`<strong class="${tone(t.pnl)}">${s.kind==='tw'?'台股':'複委託'} ${esc(t.currency)} ${signed(t.pnl)}${s.stale||cathayError?' · 上次結果':''}</strong>`)).join('')||'<strong>—</strong>')+`<small class="${failed?'report-error':''}">${demo?'虛構示範':failed?'重新讀取失敗':'檔案快照 · 非即時'}</small>`;
 $('#cathay-sources').innerHTML=sources.map(s=>`<div class="file-source"><h2>${esc(s.label)}</h2><p>${esc(s.file)} · ${s.rows.length} 筆${s.stale||cathayError?' · 保留上次成功資料':''}</p><p>${demo?'虛構示範':`基準日未提供 · 檔案修改 ${cathayDate(s.modified_at)}`}</p><div>${s.totals.map(t=>`<span>${esc(t.currency)} <strong class="${tone(t.pnl)}">${signed(t.pnl)}</strong></span>`).join('')||'<span>尚無損益合計</span>'}</div>${s.error||cathayError?`<p class="report-error">${esc(s.error||'重新讀取失敗；以上為上次成功資料。')}</p>`:''}</div>`).join('');
 const errors=sources.filter(s=>s.error);$('#cathay-report-status').textContent=demo?'虛構檔案示範；不讀取個人資料。':cathayError||errors.map(s=>s.label+'：'+s.error).join(' ')||'檔案資料已讀取；各幣別分開合計。';
 const rows=sources.flatMap(s=>(filter==='all'||filter===s.kind?s.rows:[]).filter(r=>!search||r.name.toLowerCase().includes(search)).map(r=>({...r,label:s.label})));
 $('#cathay-body').innerHTML=rows.map(r=>`<tr><td>${esc(r.label)}<small>${esc(r.market||'')}</small></td><td>${esc(r.name)}</td><td>${esc(r.currency)}</td><td>${money(r.quantity,4)}</td><td>${money(r.average,4)}</td><td>${money(r.price,4)}</td><td>${money(r.cost)}</td><td>${money(r.market_value)}</td><td class="${tone(r.pnl)}">${signed(r.pnl)}</td><td class="${tone(r.return_pct)}">${r.return_pct==null?'—':signed(r.return_pct)+'%'}</td></tr>`).join('');$('#cathay-empty').hidden=rows.length>0;$('#refresh-cathay').disabled=cathayBusy||demo||!sessionReady;
}
async function loadCathay(){if(cathayBusy||demo||!sessionReady)return;cathayBusy=true;try{cathayReport=await request('cathay');cathayError='';}catch(e){cathayError='檔案功能無法讀取。若剛更新程式，請重新啟動投資簿；已有數值保留為上次讀取結果。';}finally{cathayBusy=false;renderCathay();}}
$('#refresh-cathay').addEventListener('click',loadCathay);$('#cathay-filter').addEventListener('change',renderCathay);$('#cathay-search').addEventListener('input',renderCathay);
