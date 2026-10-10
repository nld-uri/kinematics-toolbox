function x = kin_int_tikhonov(a, dt, order, fc, pen)
%KIN_INT_TIKHONOV Regularised integration: min ||D^order x/dt^order - a||^2 + lam||Lx||^2
%   With pen=0 (L=I) the response is exact integration times a maximally flat
%   high-pass of corner fc, so lam = (2*pi*fc)^(2*order).
if nargin < 5 || isempty(pen), pen = 0; end
a = a(:);  n = numel(a);
if pen == 0, lam = (2*pi*fc)^(2*order); else, lam = (2*pi*fc)^(2*(order-pen)); end
D = kin_diffmat(n, order, dt);
b = a;
for k = 1:order, b = 0.5*(b(2:end) + b(1:end-1)); end
if pen == 0, L = speye(n); else, L = kin_diffmat(n, pen, dt); end
x = (D'*D + lam*(L'*L)) \ (D'*b);
end
