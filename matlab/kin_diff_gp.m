function [mu, sd] = kin_diff_gp(x, dt, ell, sigma_n, order, jitter)
%KIN_DIFF_GP Gaussian-process derivative, squared-exponential kernel, O(N^3).
%
%   [mu, sd] = kin_diff_gp(x, dt, ell, sigma_n, order, jitter)
%
%   The derivative of a GP is a GP, so the posterior mean of d^order x/dt^order
%   and its posterior standard deviation are available in closed form:
%       mu = K_d (K + sn^2 I)^-1 x ,   var = k_dd - diag(K_d (K + sn^2 I)^-1 K_d')
%   Kernel k(t,t') = sf2*exp(-(t-t')^2/(2 ell^2)) with sf2 = var(x) (population).
%
%   ell     : length scale in s (default 20*dt -- arbitrary; tune it).
%   sigma_n : noise std (default from kin_noisevar).
%   order   : 1 or 2.
%
%   Dense: memory ~ 4 N^2 doubles (N = 6000 needs ~1.2 GB).  Included as the
%   cleanest statement of what the quadratic-penalty methods do; for long
%   records use kin_smooth, the O(N) state-space form of the same idea.

if nargin < 5 || isempty(order), order = 1; end
if nargin < 6 || isempty(jitter), jitter = 1e-10; end
x = x(:);  n = numel(x);  t = (0:n-1)'*dt;
if nargin < 4 || isempty(sigma_n), sigma_n = sqrt(kin_noisevar(x, dt)); end
if nargin < 3 || isempty(ell), ell = 20*dt; end
sf2 = var(x, 1);
d  = t - t';                                    % d(i,j) = t_i - t_j
K  = sf2*exp(-0.5*(d/ell).^2);
Lc = chol(K + (sigma_n^2 + jitter)*eye(n), 'lower');
a  = Lc' \ (Lc \ x);
switch order
    case 1
        Kd  = K .* (-d/ell^2);
        Kdd = sf2/ell^2;
    case 2
        Kd  = K .* ((d.^2 - ell^2)/ell^4);
        Kdd = 3*sf2/ell^4;
    otherwise
        error('kin_diff_gp: order must be 1 or 2');
end
mu = Kd*a;
if nargout > 1
    V  = Lc \ Kd';
    sd = sqrt(max(Kdd - sum(V.^2, 1)', 0));
end
end
