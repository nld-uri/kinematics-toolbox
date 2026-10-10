function [y, s] = kin_diff_whittaker(x, dt, order, fc, p, lam)
%KIN_DIFF_WHITTAKER Smooth with a p-th difference penalty, then difference.
%   min_s ||s-x||^2 + lam*||D^p s/dt^p||^2 ,  lam = (2*pi*fc)^(-2p)
%   Response 1/(1+lam*w^(2p)) so fc is the -3 dB corner in Hz.
if nargin < 5 || isempty(p), p = 3; end
if nargin < 6 || isempty(lam), lam = (2*pi*fc)^(-2*p); end
x = x(:);  n = numel(x);
D = kin_diffmat(n, p, dt);
s = (speye(n) + lam*(D'*D)) \ x;
y = s;
for k = 1:order
    g = zeros(n,1);
    g(2:n-1) = (y(3:n) - y(1:n-2))/(2*dt);
    g(1)   = (-3*y(1) + 4*y(2) - y(3))/(2*dt);
    g(n)   = ( 3*y(n) - 4*y(n-1) + y(n-2))/(2*dt);
    y = g;
end
end
