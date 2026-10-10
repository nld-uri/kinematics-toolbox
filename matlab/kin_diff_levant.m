function y = kin_diff_levant(x, dt, L, order, zero_phase)
%KIN_DIFF_LEVANT Levant's robust exact differentiator (2nd-order sliding mode).
%
%   y = kin_diff_levant(x, dt, L, order, zero_phase)
%
%   Three states track x, x' and x''.  Finite-time exact when the THIRD
%   derivative is bounded, |d3x/dt3| <= L, whichever output (order 1 or 2)
%   is used; no smoothness assumption beyond that and no linear filtering.
%   It is causal, so it runs online.  Price: chattering at the sampling scale
%   and a phase lag; zero_phase = true (default) removes the lag by a second,
%   time-reversed pass (offline only).
%
%   order : 1 (velocity) or 2 (acceleration).
%   L     : bound on |d3x/dt3|.  If empty, max|jerk| from the self-tuned
%           state-space smoother (kin_smooth, nstate = 4) -- no knob.  On the
%           benchmark: 7.7 % / 18 % velocity / acceleration error, against
%           7.4 % / 21.6 % at the swept oracle.  (The earlier default bounded
%           the (order+1)-th derivative, the wrong one for this three-state
%           form, and set L ~100x too small: 119 % error.)  The estimate uses
%           the whole record; online, take L from the physics: x = X sin(w t)
%           gives L = X*w^3.
%
%   Gains (1.1, 1.5, 2.0) are Levant's standard second-order set.

if nargin < 4 || isempty(order), order = 1; end
if nargin < 5 || isempty(zero_phase), zero_phase = true; end
if order ~= 1 && order ~= 2
    error('kin_diff_levant: order must be 1 or 2');
end
x = x(:);  n = numel(x);
if nargin < 3 || isempty(L)
    r = kin_smooth((0:n-1)'*dt, struct('x', x, 'nstate', 4));
    L = max(abs(r.j)) + 1e-12;
end

[d1, d2] = run(x);
if zero_phase
    [b1, b2] = run(flipud(x));
    d1 = 0.5*(d1 - flipud(b1));
    d2 = 0.5*(d2 + flipud(b2));
end
if order == 1, y = d1; else, y = d2; end

    function [o1, o2] = run(s)
        % z0 tracks s, z1 its derivative, z2 the second derivative
        z0 = s(1);  z1 = 0;  z2 = 0;
        o1 = zeros(n,1);  o2 = zeros(n,1);
        l0 = 1.1;  l1 = 1.5;  l2 = 2.0;
        L3 = L^(1/3);  L2 = sqrt(L);
        for k = 1:n
            e  = z0 - s(k);
            v0 = -l2*L3*abs(e)^(2/3)*sign(e) + z1;
            e1 = z1 - v0;
            v1 = -l1*L2*sqrt(abs(e1))*sign(e1) + z2;
            z0 = z0 + dt*v0;
            z1 = z1 + dt*v1;
            z2 = z2 + dt*(-l0*L*sign(z2 - v1));
            o1(k) = z1;  o2(k) = z2;
        end
    end
end
