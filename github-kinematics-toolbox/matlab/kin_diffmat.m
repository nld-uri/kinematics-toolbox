function D = kin_diffmat(n, order, dt)
%KIN_DIFFMAT Sparse (n-order)-by-n finite-difference operator, scaled by dt^-order.
D = speye(n);
for k = 1:order
    m = size(D,1);
    D = spdiags([-ones(m-1,1) ones(m-1,1)], [0 1], m-1, m) * D;
end
D = D / dt^order;
end
