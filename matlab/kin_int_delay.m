function [y, info] = kin_int_delay(a, dt, order, fc, opt)
%KIN_INT_DELAY Integrate through the delay reconstruction, drift removed in delay space.
%
%   [y, info] = kin_int_delay(a, dt, order, fc, opt)
%
%   The acceleration is projected onto its signal subspace with every
%   component of mean frequency below fc (Hz) discarded -- drift, offset,
%   slow baseline -- and the reconstruction is integrated by kin_int_tikhonov
%   with corner opt.fc_int.  The default basis, 'sod', orders the subspace by
%   smoothness, so slow components separate from the oscillatory ones; with
%   'svd' they stay mixed by energy and drift survives.
%
%   order : 1 (velocity) or 2 (displacement, default).  fc default 4 Hz.
%   opt   : .fc_int (default fc for order 2, fc/4 for order 1), .L (default
%           min(floor(n/10), 2000)), .method ('sod'), .rank, .fmax, .scale.
%
%   Benchmark (1 % white + 0.5 % drift + 0.5 % offset, seed 7, fc = 4 Hz):
%   displacement 0.52 %, velocity 1.34 % ('svd': 0.72 %, 3.68 %), against
%   0.91 % / 2.04 % for oracle Tikhonov alone and 1.72 % / 1.60 % for
%   kin_smooth.  On this narrowband record the oracle spectral method is
%   better still for velocity (0.25 %).

if nargin < 3 || isempty(order), order = 2; end
if nargin < 4 || isempty(fc), fc = 4; end
if nargin < 5, opt = struct(); end
if isvector(a), a = a(:); end
n = size(a,1);
if ~isfield(opt,'L') || isempty(opt.L), opt.L = min(floor(n/10), 2000); end
if ~isfield(opt,'method') || isempty(opt.method), opt.method = 'sod'; end
if isfield(opt,'fc_int') && ~isempty(opt.fc_int), fci = opt.fc_int;
elseif order == 2, fci = fc; else, fci = fc/4; end
opt.fmin = fc;
[ar, info] = kin_delay_project(a, dt, opt);
y = zeros(size(ar));
for j = 1:size(ar,2), y(:,j) = kin_int_tikhonov(ar(:,j), dt, order, fci); end
end
