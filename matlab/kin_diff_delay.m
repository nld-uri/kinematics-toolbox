function [y, info] = kin_diff_delay(x, dt, order, opt)
%KIN_DIFF_DELAY Differentiate through the delay reconstruction (SSA / multichannel SSA).
%
%   [y, info] = kin_diff_delay(x, dt, order, opt)
%
%   x (n-by-1, or n-by-m channels processed jointly) is projected onto its
%   delay-space signal subspace by kin_delay_project (opt is passed through:
%   .L, .method, .rank, .fmax, .scale) and the reconstruction is
%   differentiated with fourth-order central differences.  The reconstruction
%   is band-limited to the signal band, where the stencil error is about
%   (w*dt)^4/30.  Self-tuning: window from the record length, dimension from
%   the Gavish-Donoho threshold, noise guard from the PSD.
%
%   Benchmark (Duffing decay, 1 % noise, seed 110): 0.32 % / 0.94 % velocity
%   / acceleration error, against 0.54 % / 1.52 % for the oracle-tuned
%   spectral method and 0.83 % / 3.33 % for the self-tuned kin_smooth.  The
%   prior suits quasi-periodic records (free decays, ringdowns, steady forced
%   response); it brings nothing at impacts, where kin_diff_tvreg wins.
%
%   order : 1 or 2.

if nargin < 3 || isempty(order), order = 1; end
if nargin < 4, opt = struct(); end
[xr, info] = kin_delay_project(x, dt, opt);
y = zeros(size(xr));
for j = 1:size(xr,2), y(:,j) = diff4(xr(:,j), dt, order); end
end

function g = diff4(s, dt, order)
n = numel(s);  g = zeros(n,1);  i = 3:n-2;
switch order
    case 1
        g(i) = (-s(i+2) + 8*s(i+1) - 8*s(i-1) + s(i-2))/(12*dt);
        e = grad2(s(1:4), dt);        g(1:2) = e(1:2);
        e = grad2(s(n-3:n), dt);      g(n-1:n) = e(3:4);
    case 2
        g(i) = (-s(i+2) + 16*s(i+1) - 30*s(i) + 16*s(i-1) - s(i-2))/(12*dt^2);
        e = grad2(grad2(s(1:5), dt), dt);      g(1:2) = e(1:2);
        e = grad2(grad2(s(n-4:n), dt), dt);    g(n-1:n) = e(4:5);
    otherwise
        error('kin_diff_delay: order must be 1 or 2');
end
end

function g = grad2(s, dt)
% numpy.gradient(s, dt, edge_order=2)
n = numel(s);  g = zeros(n,1);
g(2:n-1) = (s(3:n) - s(1:n-2))/(2*dt);
g(1) = (-3*s(1) + 4*s(2) - s(3))/(2*dt);
g(n) = ( 3*s(n) - 4*s(n-1) + s(n-2))/(2*dt);
end
