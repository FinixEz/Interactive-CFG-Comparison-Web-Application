factorial:                      # @factorial
	push	rbp
	mov	rbp, rsp
	sub	rsp, 16
	mov	dword ptr [rbp - 4], edi
	cmp	dword ptr [rbp - 4], 1
	jg	.LBB0_2
	mov	dword ptr [rbp - 8], 1
	jmp	.LBB0_3
.LBB0_2:
	mov	eax, dword ptr [rbp - 4]
	sub	eax, 1
	mov	edi, eax
	call	factorial
	imul	eax, dword ptr [rbp - 4]
	mov	dword ptr [rbp - 8], eax
.LBB0_3:
	mov	eax, dword ptr [rbp - 8]
	add	rsp, 16
	pop	rbp
	ret
