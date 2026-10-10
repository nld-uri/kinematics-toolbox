%TEST_KINEMATICS  Verify the MATLAB port against the verified Python results.
%
%   >> cd <folder containing these files>
%   >> test_kinematics
%
%   Every function is run on the same Duffing free-decay record used for the
%   Python benchmark and compared against the Python output stored in
%   kin_reference.mat.  Deviation is relative rms over the interior 90% of the
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

% ---- fusion demo: 200 Hz noisy displacement + 2 kHz drifting acceleration
rng(0);
xs = nan(n,1);  xs(1:10:end) = xt(1:10:end) + 0.03*std(xt)*randn(numel(1:10:n),1);
of = kin_smooth(t, struct('x',xs,'a',am,'nstate',4,'bias',true));
fprintf('\nfusion (200 Hz displacement + 2 kHz acceleration)\n');
fprintf('  displacement %6.3f %%   velocity %6.3f %%   acceleration %6.3f %%\n', ...
        pe(of.x,xt), pe(of.v,vt), pe(of.a,at));

fprintf('\n%d passed, %d failed\n\n', np, nf);

    function report(name, got, want, tol)
        dev = norm(got(in) - want(in)) / norm(want(in));
        ok = dev <= tol;
        fprintf('%-34s %12.3e %10.0e  %s\n', name, dev, tol, ternary(ok,'PASS','FAIL'));
        if ok, np = np + 1; else, nf = nf + 1; end
    end
end

function s = ternary(c,a,b)
if c, s = a; else, s = b; end
end
