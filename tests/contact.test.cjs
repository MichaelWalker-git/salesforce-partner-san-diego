const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync('contact.js', 'utf8');
function setup(fetch) {
    const fields = Object.fromEntries(Object.entries({fullName:' Test Visitor ',email:'test@example.com',company:'Example',message:'Synthetic workflow request',interest:'integration',website:''}).map(([k,value]) => [k,{value}]));
    const button = { disabled:false, textContent:'Get Free Assessment' };
    const status = { textContent:'' };
    let submit;
    const form = {
        elements:{namedItem:k => fields[k]},
        querySelector:() => button,
        reportValidity:() => true,
        addEventListener:(_,callback) => {submit=callback;},
        setAttribute(){},removeAttribute(){},
        reset(){for(const field of Object.values(fields))field.value='';},
    };
    vm.runInNewContext(source,{
        document:{getElementById:id => id === 'contact-form' ? form : status},
        window:{SALESFORCE_CONTACT_ENDPOINT:'https://example.com/contact',location:{search:'?utm_source=linkedin&utm_campaign=test'}},
        URLSearchParams,AbortSignal,fetch,
        FormData:class {get(k){return fields[k].value;}},
    });
    return { fields,button,status,submit:() => submit({preventDefault(){}}) };
}
test('success sends fields and campaign source, then resets only after receipt',async () => {
    let payload;
    const ui=setup(async (_,options)=>{payload=JSON.parse(options.body);return {ok:true,json:async()=>({contactId:'test-receipt'})};});
    await ui.submit();
    assert.equal(payload.name,'Test Visitor');
    assert.equal(payload.attribution.utm_source,'linkedin');
    assert.match(ui.status.textContent,/received.*test-receipt/);
    assert.equal(ui.fields.message.value,'');
    assert.equal(ui.button.disabled,false);
});
test('storage or network failure preserves entered details',async()=>{
    for(const fetch of [async()=>({ok:false,json:async()=>({error:'unavailable'})}),async()=>{throw new Error('offline');}]) {
        const ui=setup(fetch);await ui.submit();
        assert.match(ui.status.textContent,/could not confirm/);
        assert.equal(ui.fields.message.value,'Synthetic workflow request');
        assert.equal(ui.button.disabled,false);
    }
});
test('a successful HTTP response without a receipt is not reported as received',async()=>{
    const ui=setup(async()=>({ok:true,json:async()=>({})}));await ui.submit();
    assert.match(ui.status.textContent,/could not confirm/);
    assert.notEqual(ui.fields.message.value,'');
});
test('repeat submission is blocked while the first request is pending',async()=>{
    let resolve,calls=0;
    const ui=setup(()=>{calls++;return new Promise(r=>{resolve=r;});});
    const pending=ui.submit();await ui.submit();
    assert.equal(calls,1);assert.equal(ui.button.disabled,true);
    resolve({ok:true,json:async()=>({contactId:'test-receipt'})});await pending;
    assert.equal(ui.button.disabled,false);
});
