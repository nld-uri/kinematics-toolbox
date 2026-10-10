function [y, info] = kin_diff_spline(x, dt, order, fc, lam)
%KIN_DIFF_SPLINE Cubic smoothing spline, differentiated analytically at the samples.
%
%   y = kin_diff_spline(x, dt, order)            lambda by GCV (no knob)
%   y = kin_diff_spline(x, dt, order, fc)        lambda from a corner in Hz
%   y = kin_diff_spline(x, dt, order, [], lam)   lambda given directly
%   [y, info] = ...   info.lam, info.fc, info.dof (trace of the smoother), info.gcv
%
%   Solves  min_f  sum (x_i - f(t_i))^2 + lam * int f''(t)^2 dt ,
%   the same objective as scipy.interpolate.make_smoothing_spline, in the
%   Reinsch form: (R + lam*Q'Q) gamma = Q'x, f = x - lam*Q*gamma, where gamma
%   holds the second derivatives at the interior knots (natural end
%   conditions).  One pentadiagonal solve, O(N).  The derivative is read off
%   the piecewise cubic exactly; no finite differences are applied.
%
%   Tuning rule.  The data term is a sum over samples, i.e. (1/dt) times an
%   integral, so on a uniform grid the smoother response is 1/(1 + lam*dt*w^4)
%   and the -3 dB corner gives  lam = (2*pi*fc)^(-4)/dt  -- Whittaker, p = 2.
%   (The benchmark oracle lam = 3.16e-8 at dt = 5e-4 s is fc = 80 Hz.)
%
%   csaps equivalence: csaps(t, x, p) uses p = 1/(1 + lam).
%
%   GCV.  With neither fc nor lam, lam minimises the generalised
%   cross-validation score  n*||x - f||^2 / (n - tr A)^2 .  tr A is computed
%   exactly in O(N) from the band of (R + lam*Q'Q)^-1 (Takahashi selected
%   inverse).  GCV tends to under-smooth: on the benchmark Duffing record it
%   picks lam = 8.4e-9 (fc = 111 Hz) against an oracle of 3.2e-8 (80 Hz),
%   giving 1.18 % / 7.8 % velocity / acceleration error against 0.90 % / 3.7 %.
%   scipy's make_smoothing_spline returns a flat fit (100 % error) on the same
%   record, while the exact GCV score computed here has a single clear
%   minimum, so that failure lies in scipy's implementation, not in GCV.
%
%   order : 0..3.  Order 3 is piecewise constant; the value on [t_i, t_i+1)
%   is returned at t_i, and the last interval's value at t_n.
%
%   dt may be a scalar sample interval or a vector of sample times (non-uniform).

if nargin < 3 || isempty(order), order = 1; end
if nargin < 4, fc = []; end
if nargin < 5, lam = []; end
x = x(:);  n = numel(x);
if numel(dt) == n, t = dt(:); else, t = (0:n-1)'*dt; end
h = diff(t);
if n < 4, error('kin_diff_spline: need at least 4 samples'); end

% Q is n-by-(n-2) (second divided differences), Rm is (n-2)-by-(n-2) tridiagonal
i1 = 1./h(1:end-1);  i2 = 1./h(2:end);
Q  = spdiags([i1, -i1-i2, i2], [0 -1 -2], n, n-2);
Rm = spdiags([[h(2:end-1);0]/6, (h(1:end-1)+h(2:end))/3, [0;h(2:end-1)]/6], ...
             [-1 0 1], n-2, n-2);
QtQ = Q'*Q;  Qtx = Q'*x;

gcvval = NaN;
if isempty(lam)
    if ~isempty(fc)
        lam = (2*pi*fc)^(-4)/mean(h);
    else
        hm  = mean(h);                         % search corners from 1e-4 to 0.5 of fs
        lg  = linspace(log10((pi/hm)^-4/hm), log10((2*pi*1e-4/hm)^-4/hm), 41);
        gv  = arrayfun(@gcvscore, lg);
        [~, k] = min(gv);
        k1 = max(k-1,1);  k2 = min(k+1,numel(lg));
        [lgbest, gcvval] = fminbnd(@gcvscore, lg(k1), lg(k2), optimset('TolX',1e-4));
        lam = 10^lgbest;
    end
end

M = Rm + lam*QtQ;
gam = M \ Qtx;
f = x - lam*(Q*gam);
G = [0; gam; 0];                               % f'' at every knot (natural ends)

switch order
    case 0
        y = f;
    case 1
        y = zeros(n,1);
        y(1:n-1) = (f(2:n)-f(1:n-1))./h - h.*(2*G(1:n-1) + G(2:n))/6;
        y(n)     = (f(n)-f(n-1))/h(end) + h(end)*(G(n-1) + 2*G(n))/6;
    case 2
        y = G;
    case 3
        d3 = (G(2:n) - G(1:n-1))./h;
        y = [d3; d3(end)];
    otherwise
        error('kin_diff_spline: order must be 0..3');
end

if nargout > 1
    info.lam = lam;
    info.fc  = (lam*mean(h))^(-1/4)/(2*pi);
    info.dof = n - lam*trace_band(M, QtQ);
    info.gcv = gcvval;
end

    function g = gcvscore(lgl)
        L  = 10^lgl;
        Ml = Rm + L*QtQ;
        r  = L*(Q*(Ml\Qtx));                   % residual x - f
        trA = n - L*trace_band(Ml, QtQ);
        g = n*(r'*r)/(n - trA)^2;
    end
end

function s = trace_band(M, B)
%TRACE_BAND trace(M^-1 * B) for SPD pentadiagonal M and B, in O(N).
%   Only the band |i-j| <= 2 of Z = M^-1 is needed; it is obtained by the
%   Takahashi recurrence on M = L*diag(d)*L'.
m  = size(M,1);  bw = 2;
Rc = chol(M);                                  % M = Rc'*Rc, upper bidiag+1
d  = full(diag(Rc)).^2;
Lt = Rc ./ diag(Rc);                           % unit upper = L'
Lb = zeros(m, bw);                             % Lb(i,k) = L(i+k, i)
for k = 1:bw
    Lb(1:m-k, k) = full(diag(Lt, k));
end
Z = zeros(m, bw+1);                            % Z(i,k+1) = Zfull(i, i+k)
for i = m:-1:1
    kmax = min(bw, m-i);
    for jo = kmax:-1:0                         % j = i + jo, upper band of row i
        acc = 0;
        for k = 1:kmax                         % Zfull(i+k, i+jo), symmetric storage
            r = min(i+k, i+jo);  c = abs(k-jo) + 1;
            acc = acc + Lb(i,k)*Z(r, c);
        end
        Z(i, jo+1) = (jo == 0)/d(i) - acc;
    end
end
s = sum(Z(:,1).*full(diag(B)));
for k = 1:bw
    s = s + 2*sum(Z(1:m-k,k+1).*full(diag(B,k)));
end
end
