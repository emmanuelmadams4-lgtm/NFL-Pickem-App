import json,sys
d=json.load(open(sys.argv[1]))
print({k:d[k] for k in d if k in('stage','games','confirm_games','confirm_clusters','seconds','tree_chosen_on_tune')})
b=d.get('baseline');
if b: print('baseline',{m:(round(b[m]['accuracy']*100,2),round(b[m]['log_loss'],4)) for m in b},'confirm',{m:(round(d['baseline_confirm'][m]['accuracy']*100,2),round(d['baseline_confirm'][m]['log_loss'],4)) for m in b})
for c in d.get('candidates',[]):
    print(c['candidate'],'chosen',c['chosen'],'ships',c['ships'],'signal',c['signal'])
    r=c['confirm']; print('  confirm gain %.5f ci %s cluster %s acc %+.4f'%(r['log_loss_gain'],[round(x,5) for x in r['log_loss_gain_ci']],[round(x,5) for x in r['log_loss_gain_ci_cluster']],r['accuracy_diff']))
    for v in c['all_variants']: print('   %-26s tune %+.5f confirm %+.5f gap %+.5f'%(v['variant'],v['tune_gain'],v['confirm_gain'],v['gap']))
print('missing',d.get('scored_games_missing_an_input'),'eq_blend',d.get('variant_columns_equal_to_blend'))
