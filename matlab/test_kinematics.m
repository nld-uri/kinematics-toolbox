%TEST_KINEMATICS  Verify the MATLAB port against the verified Python results.
%
%   >> cd <folder containing these files>
%   >> test_kinematics
%
%   Every function is run on the same Duffing free-decay record used for the
%   Python benchmark and compared against the Python output stored in
%   kin_reference.mat.  The second block checks the routines ported later
%   (spline, Levant, GP, trapezoid+detrend) against kin_reference_ext.mat,
%   produced by the same kinematics.py (numpy 2.5.3, scipy 1.18.1); those
%   comparisons use the FULL record, ends included.  Deviation is relative rms over the interior 90% of the
%   record (the ends are excluded because MATLAB and scipy use different
%   edge conventions for Savitzky-Golay).

function test_kinematics
R = load('kin_reference.mat');
t = R.t(:);  dt = R.dt;  xm = R.x_meas(:);  am = R.a_meas(:);
n = numel(t);  k = round(0.05*n);  in = (k+1):(n-k);

fprintf('\n%-34s %12s %10s  %s\n', 'check', 'rel. dev.', 'tol', 'result');
fprintf('%s\n', repmat('-',1,72));
np = 0; nf = 0;

report('kin_diff_spectral  order 1', kin_diff_spectral(xm,dt,1,72.2), R.spec_v(:), 1e-8);
report('kin_diff_spectral  order 2', kin_diff_spectral(xm,dt,2,72.2), R.spec_a(:), 1e-8);
report('kin_diff_savgol    order 1', kin_diff_savgol(xm,dt,1,170),    R.savgol_v(:),1e-6);
report('kin_diff_whittaker order 1', kin_diff_whittaker(xm,dt,1,72.2),R.whit_v(:),  1e-8);
report('kin_diff_whittaker order 2', kin_diff_whittaker(xm,dt,2,72.2),R.whit_a(:),  1e-8);
report('kin_int_spectral   order 2', kin_int_spectral(am,dt,2,9.22),  R.ispec_x(:), 1e-8);
report('kin_int_tikhonov   order 2', kin_int_tikhonov(am,dt,2,4.18),  R.itik_x(:),  1e-8);

% std(xm,1) normalises by N, matching numpy's default; MATLAB's bare std(xm)
% uses N-1, and that 83 ppm difference in scale shows up as a 1.5e-6
% discrepancy because alpha in kin_diff_tvreg is tied to absolute signal scale.
s = std(xm, 1);
[utv, itv] = kin_diff_tvreg(xm/s, dt, 1e-4);
report('kin_diff_tvreg     order 1', utv*s, R.tv_v(:), 1e-8);
fprintf('%-34s %12s %10s  %s\n', '  tvreg converged', ...
        mat2str(itv.converged), '', sprintf('%d iters (python %d), rho=%.4g, rp/tol=%.3g rd/tol=%.3g', ...
        itv.iters, R.tv_iters, itv.rho, itv.rp_ratio, itv.rd_ratio));

o1 = kin_smooth(t, struct('x',xm,'nstate',4));
report('kin_smooth  x only -> velocity',     o1.v, R.ks_v(:), 2e-3);
report('kin_smooth  x only -> acceleration', o1.a, R.ks_a(:), 2e-3);
fprintf('%-34s %12.3e %10.0e  %s\n', 'kin_smooth  fitted q', ...
        abs(o1.q-R.ks_q)/R.ks_q, 5e-2, ternary(abs(o1.q-R.ks_q)/R.ks_q<=5e-2,'PASS','FAIL'));

o2 = kin_smooth(t, struct('a',am,'nstate',4,'bias',true,'hp',4.0));
report('kin_smooth  a only -> displacement', o2.x, R.ki_x(:), 5e-3);
report('kin_smooth  a only -> velocity',     o2.v, R.ki_v(:), 5e-3);

d = abs(kin_noisevar(xm,dt) - R.nv_x)/R.nv_x;
fprintf('%-34s %12.3e %10.0e  %s\n', 'kin_noisevar (displacement)', d, 2e-1, ...
        ternary(d<=2e-1,'PASS','FAIL'));

% ---- routines ported later; references in kin_reference_ext.mat
E = load('kin_reference_ext.mat');  ifull = 1:n;
report('kin_diff_spline    order 1', kin_diff_spline(xm,dt,1,[],E.spl_lam), E.spl_v(:), 1e-10, ifull);
report('kin_diff_spline    order 2', kin_diff_spline(xm,dt,2,[],E.spl_lam), E.spl_a(:), 1e-10, ifull);
if exist('csaps','file') == 2           % Curve Fitting Toolbox, independent check
    pp = csaps(t, xm, 1/(1+E.spl_lam));
    report('  vs csaps (p = 1/(1+lam))', kin_diff_spline(xm,dt,1,[],E.spl_lam), ...
           fnval(fnder(pp,1), t), 1e-8, in);
end
report('kin_diff_levant    order 1', kin_diff_levant(xm,dt,E.lev_L1,1), E.lev_v(:), 1e-12, ifull);
report('kin_diff_levant    order 2', kin_diff_levant(xm,dt,E.lev_L2,2), E.lev_a(:), 1e-12, ifull);
report('kin_diff_levant    causal ', kin_diff_levant(xm,dt,E.lev_L1,1,false), E.lev_vc(:), 1e-12, ifull);
report('kin_diff_levant    default L', kin_diff_levant(xm,dt,[],1), E.lev_vauto(:), 2e-3, ifull);   % L via kin_smooth jerk
ng = E.gp_n;  ig = 1:ng;
[gv, gs] = kin_diff_gp(xm(ig), dt, E.gp_ell, E.gp_sn, 1);
report('kin_diff_gp        order 1', gv, E.gp_v(:), 1e-10, ig);
report('kin_diff_gp        std    ', gs, E.gp_vsd(:), 1e-10, ig);
report('kin_diff_gp        order 2', kin_diff_gp(xm(ig), dt, E.gp_ell, E.gp_sn, 2), E.gp_a(:), 1e-10, ig);
report('kin_int_trapz_detrend v   ', kin_int_trapz_detrend(am,dt,1,1,E.itr_hp), E.itr_v(:), 1e-8, ifull);
report('kin_int_trapz_detrend x   ', kin_int_trapz_detrend(am,dt,2,1,E.itr_hp), E.itr_x(:), 1e-8, ifull);
report('kin_int_trapz_detrend no hp', kin_int_trapz_detrend(am,dt,2,1), E.itr_x_nohp(:), 1e-10, ifull);
[vg, si] = kin_diff_spline(xm, dt, 1);
report('kin_diff_spline    GCV       ', vg, E.spl_gcv_v(:), 1e-8, ifull);
fprintf('%-34s %12.3e %10.0e  %s\n', '  GCV lambda', abs(si.lam-E.spl_gcv_lam)/E.spl_gcv_lam, 1e-6, ...
        ternary(abs(si.lam-E.spl_gcv_lam)/E.spl_gcv_lam <= 1e-6, 'PASS', 'FAIL'));
if abs(si.lam-E.spl_gcv_lam)/E.spl_gcv_lam <= 1e-6, np = np + 1; else, nf = nf + 1; end
oc = kin_smooth(t, struct('x',xm,'nstate',4,'causal',true));
report('kin_smooth  causal filter    ', oc.v, E.ksc_v(:), 2e-3, ifull);

% ---- delay reconstruction (SSA / SOD)
report('kin_signal_band', kin_signal_band(xm,dt), E.sband_x, 1e-12, 1);
[vd, di] = kin_diff_delay(xm, dt, 1);
report('kin_diff_delay  svd order 1', vd, E.dd_v(:), 1e-9, ifull);
report('kin_diff_delay  svd order 2', kin_diff_delay(xm,dt,2), E.dd_a(:), 1e-9, ifull);
report('kin_diff_delay  sod        ', kin_diff_delay(xm,dt,1,struct('method','sod')), E.dd_v_sod(:), 1e-9, ifull);
report('kin_diff_delay  sod_full   ', kin_diff_delay(xm,dt,1,struct('method','sod_full','L',161)), E.dd_v_sodfull(:), 1e-9, ifull);
report('kin_diff_delay  3 channels ', kin_diff_delay(E.md_Xn,dt,1,struct('L',213)), E.md_v, 1e-9, ifull);
report('kin_int_delay   sod  x     ', kin_int_delay(am,dt,2), E.id_x(:), 1e-8, ifull);
report('kin_int_delay   sod  v     ', kin_int_delay(am,dt,1), E.id_v(:), 1e-8, ifull);
report('kin_int_delay   svd  x     ', kin_int_delay(am,dt,2,4,struct('method','svd')), E.id_x_svd(:), 1e-8, ifull);

% causal filter: no Python counterpart; filter and smoother must agree at the last sample
oq = kin_smooth(t, struct('x',xm,'nstate',4,'q',o1.q,'causal',true));
d = abs(oq.v(end) - o1.v(end))/abs(o1.v(end));
fprintf('%-34s %12.3e %10.0e  %s\n', 'kin_smooth causal = RTS at t_end', d, 1e-10, ternary(d<=1e-10,'PASS','FAIL'));
if d <= 1e-10, np = np + 1; else, nf = nf + 1; end

fprintf('%s\n', repmat('-',1,72));

% ---- accuracy against the TRUE kinematics, as a sanity check on the whole chain
vt = R.v_true(:); at = R.a_true(:); xt = R.x_true(:);
pe = @(e,g) 100*norm(e(in)-g(in))/norm(g(in));
fprintf('\nerror against ground truth (%% rms, interior 90%% of record)\n');
fprintf('  velocity  from position     : whittaker %6.3f   state-space %6.3f\n', ...
        pe(kin_diff_whittaker(xm,dt,1,72.2),vt), pe(o1.v,vt));
fprintf('  accel.    from position     : whittaker %6.3f   state-space %6.3f\n', ...
        pe(kin_diff_whittaker(xm,dt,2,72.2),at), pe(o1.a,at));
fprintf('  displacement from accel.    : tikhonov  %6.3f   state-space %6.3f\n', ...
        pe(kin_int_tikhonov(am,dt,2,4.18),xt), pe(o2.x,xt));
fprintf('  velocity  from position     : spline GCV %5.3f (fc = %.0f Hz)   spline fc = 80 Hz %6.3f\n', ...
        pe(vg,vt), si.fc, pe(kin_diff_spline(xm,dt,1,80),vt));
fprintf('  vel. / acc. from position   : delay SVD %6.3f / %6.3f  (L = %d, %d of %d components)\n', ...
        pe(vd,vt), pe(kin_diff_delay(xm,dt,2),at), di.L, sum(di.keep), di.r);
fprintf('  displacement / vel. from acc: delay SOD %6.3f / %6.3f\n', ...
        pe(kin_int_delay(am,dt,2),xt), pe(kin_int_delay(am,dt,1),vt));
fprintf('  velocity, causal estimators : Kalman filter %6.3f   Levant (L = 1330) %6.3f\n', ...
        pe(oc.v,vt), pe(kin_diff_levant(xm,dt,1330,1,false),vt));

% ---- fusion demo: 200 Hz noisy displacement + 2 kHz drifting acceleration
rng(0);
xs = nan(n,1);  xs(1:10:end) = xt(1:10:end) + 0.03*std(xt)*randn(numel(1:10:n),1);
of = kin_smooth(t, struct('x',xs,'a',am,'nstate',4,'bias',true));
fprintf('\nfusion (200 Hz displacement + 2 kHz acceleration)\n');
fprintf('  displacement %6.3f %%   velocity %6.3f %%   acceleration %6.3f %%\n', ...
        pe(of.x,xt), pe(of.v,vt), pe(of.a,at));

fprintf('\n%d passed, %d failed\n\n', np, nf);

    function report(name, got, want, tol, idx)
        if nargin < 5, idx = in; end
        dev = norm(got(idx) - want(idx)) / norm(want(idx));
        ok = dev <= tol;
        fprintf('%-34s %12.3e %10.0e  %s\n', name, dev, tol, ternary(ok,'PASS','FAIL'));
        if ok, np = np + 1; else, nf = nf + 1; end
    end
end

function s = ternary(c,a,b)
if c, s = a; else, s = b; end
end
