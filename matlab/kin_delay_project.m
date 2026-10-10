function [xr, info] = kin_delay_project(x, dt, opt)
%KIN_DELAY_PROJECT Project x onto its delay-reconstruction signal subspace.
%
%   [xr, info] = kin_delay_project(x, dt, opt)
%
%   x is n-by-1 or n-by-m (m channels, embedded side by side = multichannel
%   SSA).  Rows of the trajectory matrix are delay vectors
%   [x_k, x_k+1, ..., x_k+L-1]; the signal subspace is found, the matrix
%   projected onto it and averaged back along the anti-diagonals.
%
%   opt fields (all optional):
%     .L       window, default min(floor(n/3), 2000)
%     .method  'svd' (default)  principal directions, ranked by energy (SSA)
%              'sod'  smooth orthogonal decomposition INSIDE the SVD signal
%                     subspace: (Y'Y) phi = lam (dY'dY) phi orders it by
%                     smoothness (frequency), so slow drift separates from
%                     oscillation.  Same reconstruction as 'svd' unless a
%                     band is dropped.
%              'sod_full'  SOD of the whole embedding, ranked by smoothness
%                     only.  For comparison: long windows let smooth NOISE
%                     directions in ahead of signal.
%     .rank    'auto' (Gavish-Donoho hard threshold) or an integer
%     .fmin, .fmax   keep components whose mean frequency
%              f_k = rms(dq_k/dt)/(2*pi*rms(q_k)) lies in [fmin, fmax] Hz.
%              fmax = 'auto' (default) uses kin_signal_band(x, dt) -- a guard
%              against noise directions that pass the threshold at long
%              windows.  [] disables.
%     .scale   per-channel divisor before embedding; 'auto' = noise std of
%              each channel when m > 1 (equal-variance noise, as the
%              threshold assumes), 1 for a single channel.
%
%   info: r (threshold rank), keep, f (Hz), sv, L, fmax, scale.

if nargin < 3, opt = struct(); end
if isvector(x), x = x(:); end
[n, m] = size(x);
L = getdef(opt, 'L', min(floor(n/3), 2000));
method = getdef(opt, 'method', 'svd');
rnk = getdef(opt, 'rank', 'auto');
fmin = getdef(opt, 'fmin', []);
if isfield(opt, 'fmax'), fmax = opt.fmax; else, fmax = 'auto'; end
scale = getdef(opt, 'scale', 'auto');
if ischar(scale)
    if m > 1
        scale = zeros(1, m);
        for j = 1:m, scale(j) = sqrt(kin_noisevar_scipy(x(:,j), dt)); end
    else
        scale = 1;
    end
end
scale = reshape(scale, 1, m);
if ischar(fmax), fmax = kin_signal_band(x, dt); end

K = n - L + 1;
idx = (0:K-1)' + (1:L);                       % K-by-L delay indices
X = zeros(K, L*m);
for j = 1:m
    xj = x(:,j) / scale(j);
    X(:, (j-1)*L + (1:L)) = xj(idx);
end
C = X'*X;  C = 0.5*(C + C');
[V, S2] = eig(C, 'vector');
[S2, o] = sort(S2, 'descend');  V = V(:, o);
sv = sqrt(max(S2, 0));
if ischar(rnk)
    p = L*m;  beta = min(K,p)/max(K,p);
    om = 0.56*beta^3 - 0.95*beta^2 + 1.82*beta + 1.43;
    r = sum(sv > om*median(sv));
else
    r = rnk;
end
r = max(1, min(r, L*m));
switch method
    case 'svd'
        B = V(:,1:r);  Bi = B';
    case 'sod'
        Y = X*V(:,1:r);  dY = diff(Y);
        A1 = Y'*Y/K;  A2 = dY'*dY/(K-1);
        [Phi, lam] = eig(0.5*(A1+A1'), 0.5*(A2+A2'), 'chol', 'vector');
        [~, o] = sort(lam, 'descend');  Phi = Phi(:, o);
        B = V(:,1:r)*Phi;  Bi = Phi \ V(:,1:r)';
    case 'sod_full'
        dX = diff(X);  A2 = dX'*dX/(K-1);
        [Phi, lam] = eig(C/K, 0.5*(A2+A2'), 'chol', 'vector');
        [~, o] = sort(lam, 'descend');  Phi = Phi(:, o);
        Pi = inv(Phi);  B = Phi(:,1:r);  Bi = Pi(1:r,:);
    otherwise
        error('kin_delay_project: method must be svd, sod or sod_full');
end
Q = X*B;
f = sqrt(mean(diff(Q).^2, 1) ./ mean(Q.^2, 1))' / (2*pi*dt);
keep = true(r, 1);
if ~isempty(fmin), keep = keep & f >= fmin; end
if ~isempty(fmax), keep = keep & f <= fmax; end
Xr = Q(:,keep) * Bi(keep,:);

% anti-diagonal averaging, channel by channel
cnt = accumarray(idx(:), 1, [n 1]);
xr = zeros(n, m);
for j = 1:m
    blk = Xr(:, (j-1)*L + (1:L));
    xr(:,j) = accumarray(idx(:), blk(:), [n 1]) ./ cnt * scale(j);
end
info = struct('r', r, 'keep', keep, 'f', f, 'sv', sv, 'L', L, ...
              'fmax', fmax, 'scale', scale);
end

function v = getdef(s, f, d)
if isfield(s, f) && ~isempty(s.(f)), v = s.(f); else, v = d; end
end

function s2 = kin_noisevar_scipy(y, dt)
% noise variance from the PSD plateau with the scipy Welch conventions
% (matches the Python estimate_noise_var, nperseg = min(n, 4096))
[f, P] = welch_lin(y(:), dt, min(numel(y), 4096));
m = f >= 0.40/dt & f <= 0.49/dt;
if ~any(m), m = f >= 0.8*f(end); end
s2 = median(P(m)) * (0.5/dt);
end

function [f, P] = welch_lin(y, dt, nps)
y = y - mean(y);  n = numel(y);  step = nps - floor(nps/2);
w = 0.5 - 0.5*cos(2*pi*(0:nps-1)'/nps);
tt = (0:nps-1)';  A = [tt ones(nps,1)];
nseg = floor((n - nps)/step) + 1;  P = 0;
for s = 0:nseg-1
    seg = y(s*step + (1:nps));
    seg = seg - A*(A\seg);
    Y = fft(seg.*w);
    P = P + abs(Y(1:floor(nps/2)+1)).^2;
end
P = P / (nseg * sum(w.^2) / dt);
if mod(nps,2) == 0, P(2:end-1) = 2*P(2:end-1); else, P(2:end) = 2*P(2:end); end
f = (0:floor(nps/2))' / (nps*dt);
end
