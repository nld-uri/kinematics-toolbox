function out = kin_smooth(t, opt)
%KIN_SMOOTH Kinematic Kalman/RTS smoother: differentiate, integrate, or fuse.
%
%   out = kin_smooth(t, opt) with opt a struct of options:
%     .x, .v, .a   measurement vectors (NaN = missing sample).  Give any subset.
%     .Rx,.Rv,.Ra  measurement-noise variances (estimated from the data if absent)
%     .nstate      number of kinematic states [x v a jerk ...]      (default 4)
%     .bias        true to add a random-walk accelerometer-offset state (false)
%     .hp          high-pass corner in Hz -- REQUIRED when integrating
%                  acceleration alone, since x and mean v are then unobservable
%     .q           process-noise PSD; omitted => fitted by marginal likelihood
%     .causal      true to return the forward Kalman FILTER estimates instead
%                  of the RTS smoother: each output sample uses only data up
%                  to that time, so it can run online (lag, larger error).
%                  For true online use fit .q once on a calibration record
%                  and pass it in; the default fit uses the whole record.
%
%   State model: white noise on the nstate-th derivative (integrated random
%   walk).  No model of the system is used -- only the assertion that the
%   signal is smooth.  Returns out.x, out.v, out.a, out.std, out.q, out.loglik.
%
%   x only  -> differentiation      a only  -> integration (needs .hp)
%   x and a -> complementary fusion (no .hp needed: x observes the low end)

if nargin < 2, opt = struct(); end
t = t(:);  n = numel(t);
dts = diff(t);  dt0 = dts(1);
uniform = all(abs(dts - dt0) < 1e-9*abs(dt0));
g = @(f,d) getfielddef(opt,f,d);
nstate = g('nstate',4);  bias = g('bias',false);  hp = g('hp',[]);

names = {'x','v','a'};  idx = [1 2 3];  Rf = {'Rx','Rv','Ra'};
Y = [];  H = [];  R = [];  isacc = [];
ns = nstate + double(bias);
for k = 1:3
    if isfield(opt, names{k}) && ~isempty(opt.(names{k}))
        y = opt.(names{k})(:);
        r = g(Rf{k}, []);
        if isempty(r), r = kin_noisevar(y(isfinite(y)), dt0); end
        h = zeros(1, ns);  h(idx(k)) = 1;
        if bias && k == 3, h(nstate+1) = 1; end
        Y = [Y, y];  H = [H; h];  R = [R, max(r,1e-30)];  isacc = [isacc, k==3];
    end
end
if isempty(Y), error('kin_smooth: give at least one of x, v, a'); end

q = g('q', []);
if isempty(q)
    scale = var(Y(isfinite(Y(:,1)),1)) / dt0^(2*nstate-1);
    f = @(lg) -loglik(10^lg*scale);
    lg = fminbnd(f, -14, 6, optimset('TolX',1e-3));
    q = 10^lg * scale;
end
if ~isempty(hp)
    wc = 2*pi*hp;
    H = [H; [1 zeros(1,ns-1)]; [0 1 zeros(1,ns-2)]];
    R = [R, q/wc^(2*nstate), q/wc^(2*nstate-2)];
    Y = [Y, zeros(n,2)];
end
if g('causal', false)
    [ms, Ps, ll] = kfilter(q, true);
else
    [ms, Ps, ll] = smoother(q);
end
out.x = ms(:,1);  out.v = ms(:,2);  out.a = ms(:,3);
if nstate > 3, out.j = ms(:,4); end
if bias, out.bias = ms(:,nstate+1); end
sd = zeros(n, ns);
for k = 1:n, sd(k,:) = sqrt(max(diag(Ps(:,:,k)),0))'; end
out.std = sd;  out.q = q;  out.loglik = ll;  out.R = R;

    function [F,Q] = fq(dt, qv)
        F = eye(ns);  Q = zeros(ns);
        for i = 1:nstate
            for j = i:nstate
                F(i,j) = dt^(j-i)/factorial(j-i);
            end
        end
        for i = 1:nstate
            for j = 1:nstate
                p = 2*nstate - i - j + 1;
                Q(i,j) = qv*dt^p / (factorial(nstate-i)*factorial(nstate-j)*p);
            end
        end
        if bias
            F(nstate+1,nstate+1) = 1;
            Q(nstate+1,nstate+1) = getfielddef(opt,'qbias',qv*1e-6)*dt;
        end
    end

    function ll = loglik(qv)
        [~,~,ll] = kfilter(qv, false);
        ll = ll / n;
    end

    function [ms,Ps,ll] = smoother(qv)
        [mf,Pf,ll,mp,Pp,Fs] = kfilter(qv, true);
        ms = mf;  Ps = Pf;
        for k = n-1:-1:1
            Fk = Fs(:,:,k+1);
            G = Pf(:,:,k)*Fk'*pinv(Pp(:,:,k+1));
            ms(k,:) = mf(k,:) + (G*(ms(k+1,:)-mp(k+1,:))')';
            Ps(:,:,k) = Pf(:,:,k) + G*(Ps(:,:,k+1)-Pp(:,:,k+1))*G';
        end
    end

    function [mf,Pf,ll,mp,Pp,Fs] = kfilter(qv, keep)
        m = zeros(ns,1);  P = eye(ns)*1e6;
        if bias, P(nstate+1,nstate+1) = 1e2; end
        mf = zeros(n,ns);  Pf = zeros(ns,ns,n);
        mp = zeros(n,ns);  Pp = zeros(ns,ns,n);  Fs = zeros(ns,ns,n);
        ll = 0;  Fc = [];  Qc = [];
        for k = 1:n
            if k > 1
                if uniform
                    if isempty(Fc), [Fc,Qc] = fq(dt0,qv); end
                    F = Fc;  Q = Qc;
                else
                    [F,Q] = fq(dts(k-1), qv);
                end
                m = F*m;  P = F*P*F' + Q;
                if keep, Fs(:,:,k) = F; end
            end
            if keep, mp(k,:) = m';  Pp(:,:,k) = P; end
            obs = isfinite(Y(k,:));
            if any(obs)
                Hk = H(obs,:);  Rk = diag(R(obs));
                S = Hk*P*Hk' + Rk;  S = 0.5*(S+S');
                innov = Y(k,obs)' - Hk*m;
                K = P*Hk'/S;
                m = m + K*innov;  P = P - K*Hk*P;  P = 0.5*(P+P');
                ll = ll - 0.5*(innov'*(S\innov)) - 0.5*log(det(S)) ...
                        - 0.5*numel(innov)*log(2*pi);
            end
            mf(k,:) = m';  Pf(:,:,k) = P;
        end
    end
end

function v = getfielddef(s, f, d)
if isfield(s,f) && ~isempty(s.(f)), v = s.(f); else, v = d; end
end
