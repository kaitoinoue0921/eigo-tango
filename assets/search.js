(function(){
  var up=document.body.getAttribute('data-up')||'';
  var q=document.getElementById('q'),sug=document.getElementById('sug');
  if(!q)return;
  var idx=null,loading=null,cur=-1,hits=[];
  function load(){
    if(idx)return Promise.resolve(idx);
    if(!loading)loading=fetch(up+'assets/index.json').then(function(r){return r.json()}).then(function(j){idx=j;return j}).catch(function(){loading=null;return []});
    return loading;
  }
  function search(t){
    t=t.trim().toLowerCase();
    if(!t)return[];
    var pre=[],inc=[],seen={};
    for(var e=0;e<idx.length;e++){if(idx[e][0]===t){pre.push(idx[e])}}
    for(var i=0;i<idx.length&&pre.length<8;i++){
      var r=idx[i];
      if(r[0]!==t&&r[0].indexOf(t)===0){pre.push(r)}
    }
    if(pre.length<8){
      for(var j=0;j<idx.length&&pre.length+inc.length<8;j++){
        var s=idx[j];
        if(s[0].indexOf(t)>0)inc.push(s);
        else if(/[^\x00-\x7f]/.test(t)&&s[2].indexOf(t)>=0)inc.push(s);
      }
    }
    return pre.concat(inc).filter(function(r){var k=r[0]+'>'+r[1];if(seen[k])return false;seen[k]=1;return true});
  }
  function esc(s){return s.replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
  function render(){
    if(!q.value.trim()){sug.hidden=true;return}
    if(!hits.length){sug.innerHTML='<li class="none">見つかりませんでした</li>';sug.hidden=false;return}
    sug.innerHTML=hits.map(function(r,i){
      var label=r[0]!==r[1]?esc(r[0])+' → '+esc(r[1]):esc(r[0]);
      return '<li'+(i===cur?' class="on"':'')+'><a href="'+up+'w/'+encodeURIComponent(r[1])+'.html"><b>'+label+'</b><span>'+esc(r[2])+'</span></a></li>'
    }).join('');
    sug.hidden=false;
  }
  function update(){load().then(function(){hits=search(q.value);cur=-1;render()})}
  q.addEventListener('input',update);
  q.addEventListener('focus',function(){load()});
  q.addEventListener('keydown',function(e){
    if(e.key==='ArrowDown'){e.preventDefault();cur=Math.min(cur+1,hits.length-1);render()}
    else if(e.key==='ArrowUp'){e.preventDefault();cur=Math.max(cur-1,0);render()}
    else if(e.key==='Enter'){var r=hits[cur>=0?cur:0];if(r)location.href=up+'w/'+encodeURIComponent(r[1])+'.html'}
    else if(e.key==='Escape'){sug.hidden=true}
  });
  document.addEventListener('click',function(e){if(!e.target.closest('.sform'))sug.hidden=true});
  document.addEventListener('keydown',function(e){if(e.key==='/'&&document.activeElement!==q&&!/input|textarea/i.test(document.activeElement.tagName)){e.preventDefault();q.focus()}});
})();
